"""Luật trạng thái của case test tay (Manual): không gửi duyệt, test xong là TESTED."""

import pytest

from app.core.models.test_case import (
    ExecutionMode,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
)
from app.core.services.test_cases import (
    MANUAL_NO_REVIEW,
    CaseAction,
    InvalidTransitionError,
)
from tests.test_test_case_service import (
    LEAD,
    TESTER_A,
    EditSink,
    Env,
    env,  # noqa: F401  (fixture dùng chung)
    service_with,
)
from tests.test_test_case_service import (
    content as automation_content,
)


def content(title: str = "Đăng nhập đúng") -> TestCaseContent:
    """Nội dung case test tay (fixture dùng chung mặc định là Automation)."""
    return automation_content(title).model_copy(update={"execution_mode": ExecutionMode.MANUAL})


def make_manual(env: Env) -> TestCase:  # noqa: F811
    return env.service.create(TESTER_A, screen_id="SC-0001", content=content())


def make_automation(env: Env) -> TestCase:  # noqa: F811
    return env.service.create(
        TESTER_A,
        screen_id="SC-0001",
        content=automation_content(),
    )


def test_manual_case_cannot_be_submitted(env: Env) -> None:  # noqa: F811
    case = make_manual(env)

    with pytest.raises(InvalidTransitionError) as error:
        env.service.transition(TESTER_A, case.id, CaseAction.SUBMIT, version=1)

    assert str(error.value) == MANUAL_NO_REVIEW


def test_mark_tested_moves_draft_to_tested_with_audit(env: Env) -> None:  # noqa: F811
    case = make_manual(env)

    saved = env.service.mark_tested(TESTER_A, case.id, version=1)

    assert saved.status == TestCaseStatus.TESTED
    assert env.service.history(case.id)[0].action == "MANUAL_TEST"


def test_mark_tested_when_already_tested_keeps_version(env: Env) -> None:  # noqa: F811
    case = make_manual(env)
    tested = env.service.mark_tested(TESTER_A, case.id, version=1)
    rows = env.audit_rows()

    again = env.service.mark_tested(TESTER_A, case.id, version=tested.version)

    assert again.status == TestCaseStatus.TESTED
    assert again.version == tested.version
    assert env.audit_rows() == rows


def test_mark_tested_rejects_automation_case(env: Env) -> None:  # noqa: F811
    case = make_automation(env)

    with pytest.raises(InvalidTransitionError):
        env.service.mark_tested(TESTER_A, case.id, version=1)


def test_editing_tested_manual_case_returns_to_draft(env: Env) -> None:  # noqa: F811
    case = make_manual(env)
    tested = env.service.mark_tested(TESTER_A, case.id, version=1)

    saved = env.service.update_content(
        TESTER_A, case.id, version=tested.version, content=content("Tiêu đề khác")
    )

    assert saved.status == TestCaseStatus.DRAFT
    assert env.service.history(case.id)[0].diff["status"] == ["TESTED", "DRAFT"]


def test_switching_mode_returns_to_draft(env: Env) -> None:  # noqa: F811
    # Automation đã duyệt -> đổi sang Manual
    auto = make_automation(env)
    approved = env.service.transition(TESTER_A, auto.id, CaseAction.SUBMIT, version=1)
    approved = env.service.transition(LEAD, auto.id, CaseAction.APPROVE, version=approved.version)
    assert approved.status == TestCaseStatus.APPROVED
    to_manual = env.service.update_content(
        TESTER_A, auto.id, version=approved.version, content=content()
    )
    assert to_manual.status == TestCaseStatus.DRAFT

    # Manual đã test -> đổi sang Automation
    manual = make_manual(env)
    tested = env.service.mark_tested(TESTER_A, manual.id, version=1)
    to_auto = env.service.update_content(
        TESTER_A,
        manual.id,
        version=tested.version,
        content=automation_content(),
    )
    assert to_auto.status == TestCaseStatus.DRAFT


def test_manual_edit_never_requests_rerun(env: Env) -> None:  # noqa: F811
    sink = EditSink()
    service = service_with(env, review=False, sink=sink, has_results=True)
    case = service.create(TESTER_A, screen_id="SC-0001", content=content())
    tested = service.mark_tested(TESTER_A, case.id, version=1)
    changed = content().model_copy(update={"steps": [content().steps[0].model_copy(
        update={"action": "Bước mới"}
    )]})

    saved = service.update_content(TESTER_A, case.id, version=tested.version, content=changed)

    assert saved.status == TestCaseStatus.DRAFT
    assert sink.edits == []


def test_deprecate_allowed_from_tested_for_manual(env: Env) -> None:  # noqa: F811
    case = make_manual(env)
    tested = env.service.mark_tested(TESTER_A, case.id, version=1)

    saved = env.service.transition(
        TESTER_A, case.id, CaseAction.DEPRECATE, version=tested.version
    )

    assert saved.status == TestCaseStatus.DEPRECATED


def test_deprecate_from_tested_still_rejected_for_automation(env: Env) -> None:  # noqa: F811
    case = make_automation(env)
    # đưa thẳng sang TESTED như agent làm (qua repository) để thử luật
    env.test_cases.save(
        case.model_copy(update={"status": TestCaseStatus.TESTED}),
        expected_version=1,
        actor="a@x.com",
    )

    with pytest.raises(InvalidTransitionError):
        env.service.transition(TESTER_A, case.id, CaseAction.DEPRECATE, version=2)

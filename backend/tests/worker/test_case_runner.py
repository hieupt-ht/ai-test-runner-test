from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, StorageState

from app.core.models.run import ResultStatus
from app.core.models.test_case import (
    AutoStep,
    AutoTarget,
    AutoType,
    Priority,
    Severity,
    TargetBy,
    TestCase,
    TestCaseStatus,
    TestStep,
)
from app.worker.case_runner import (
    CaseSession,
    LoginError,
    blocked_reason,
    perform_login,
)
from app.worker.config import ProjectWorkerConfig

PASSWORD = "s3cret-pass-123"


def auto(type_: AutoType, value: str = "", by: TargetBy | None = None, on: str = "") -> AutoStep:
    target = AutoTarget(by=by, value=on) if by is not None else None
    return AutoStep(type=type_, target=target, value=value)


def make_case(*steps: TestStep, case_id: str = "TC-000001") -> TestCase:
    moment = datetime(2026, 11, 14, tzinfo=UTC)
    return TestCase(
        id=case_id,
        screen_id="SC-0001",
        title="Một case",
        steps=list(steps),
        expected_result="ổn",
        severity=Severity.HIGH,
        priority=Priority.P1,
        status=TestCaseStatus.APPROVED,
        created_by="a@x.com",
        updated_by="a@x.com",
        created_at=moment,
        updated_at=moment,
        version=1,
    )


def step(action: str, auto_step: AutoStep | None = None) -> TestStep:
    return TestStep(action=action, expected="", auto=auto_step)


class ExplodingBrowser:
    """Nếu code mở trình duyệt (cho case bị chặn) thì test sẽ nổ."""

    def new_context(self, **_: Any) -> None:
        raise AssertionError("không được mở trình duyệt cho case BLOCKED")


def make_config(site: str) -> ProjectWorkerConfig:
    return ProjectWorkerConfig(
        app_path=".",
        start_command="x",
        app_url=site,
        test_email="qa@x.com",
        test_password=PASSWORD,
        login_steps=[
            auto(AutoType.GOTO, "/login"),
            auto(AutoType.FILL, "{email}", TargetBy.LABEL, "Email"),
            auto(AutoType.FILL, "{password}", TargetBy.LABEL, "Mật khẩu"),
            auto(AutoType.CLICK, "", TargetBy.TEXT, "Đăng nhập"),
        ],
    )


def make_session(
    browser: Browser | ExplodingBrowser,
    site: str,
    tmp_path: Path,
    *,
    storage_state: StorageState | None = None,
    case_timeout_seconds: float = 30,
) -> CaseSession:
    return CaseSession(
        browser,  # type: ignore[arg-type]
        storage_state,
        site,
        tmp_path,
        "RUN-0001",
        step_timeout_ms=800,
        case_timeout_seconds=case_timeout_seconds,
    )


def test_blocked_when_no_step_has_auto() -> None:
    case = make_case(step("Mở trang"), step("Bấm nút"))

    assert blocked_reason(case) == "Chưa có bước tự động"


def test_blocked_names_first_step_missing_auto() -> None:
    case = make_case(step("Mở", auto(AutoType.GOTO, "/form")), step("Bấm"), step("Kiểm tra"))

    assert blocked_reason(case) == "Bước 2 chưa có phần tự động"


def test_complete_case_is_not_blocked() -> None:
    assert blocked_reason(make_case(step("Mở", auto(AutoType.GOTO, "/form")))) is None


def test_partially_automated_case_is_blocked_without_opening_browser(tmp_path: Path) -> None:
    case = make_case(step("Mở", auto(AutoType.GOTO, "/form")), step("Bấm"))
    session = make_session(ExplodingBrowser(), "http://x", tmp_path)

    outcome = session.run(case)

    assert outcome.status == ResultStatus.BLOCKED
    assert "Bước 2" in outcome.reason
    assert outcome.screenshot is None


def test_pass_when_all_steps_pass(browser: Browser, site: str, tmp_path: Path) -> None:
    case = make_case(
        step("Mở form", auto(AutoType.GOTO, "/form")),
        step("Bấm Gửi", auto(AutoType.CLICK, "", TargetBy.TEXT, "Gửi")),
        step("Thấy thông báo", auto(AutoType.SEE_TEXT, "Đã gửi")),
    )

    outcome = make_session(browser, site, tmp_path).run(case)

    assert outcome.status == ResultStatus.PASS
    assert outcome.failed_step is None
    assert outcome.screenshot is None


def test_fail_reports_step_number_and_screenshot(
    browser: Browser, site: str, tmp_path: Path
) -> None:
    case = make_case(
        step("Mở form", auto(AutoType.GOTO, "/form")),
        step("Thấy chữ sai", auto(AutoType.SEE_TEXT, "Chữ không tồn tại")),
        step("Không chạy tới", auto(AutoType.SEE_TEXT, "Biểu mẫu")),
    )

    outcome = make_session(browser, site, tmp_path).run(case)

    assert outcome.status == ResultStatus.FAIL
    assert outcome.failed_step == 2
    assert 'Không thấy chữ "Chữ không tồn tại"' in outcome.reason
    assert outcome.screenshot == tmp_path / "RUN-0001" / "TC-000001.png"
    assert outcome.screenshot.is_file()
    assert outcome.screenshot.stat().st_size > 0


def test_case_timeout_is_inconclusive(browser: Browser, site: str, tmp_path: Path) -> None:
    case = make_case(
        step("Mở form", auto(AutoType.GOTO, "/form")),
        step("Chờ mãi", auto(AutoType.SEE_TEXT, "Chữ không tồn tại")),
    )

    outcome = make_session(browser, site, tmp_path, case_timeout_seconds=0.5).run(case)

    assert outcome.status == ResultStatus.INCONCLUSIVE
    assert "quá" in outcome.reason


def test_cases_do_not_share_state(browser: Browser, site: str, tmp_path: Path) -> None:
    session = make_session(browser, site, tmp_path)
    fill_name = step(
        "Điền tên",
        auto(AutoType.FILL, "An", TargetBy.LABEL, "Họ tên"),
    )
    first = make_case(step("Mở", auto(AutoType.GOTO, "/form")), fill_name, case_id="TC-000001")
    second = make_case(
        step("Mở", auto(AutoType.GOTO, "/form")),
        step("Ô tên còn trống", auto(AutoType.NOT_SEE_TEXT, "An")),
        case_id="TC-000002",
    )

    assert session.run(first).status == ResultStatus.PASS
    assert session.run(second).status == ResultStatus.PASS


def test_login_session_is_reused(browser: Browser, site: str, tmp_path: Path) -> None:
    state = perform_login(browser, make_config(site), step_timeout_ms=800)
    case = make_case(
        step("Mở trang chủ", auto(AutoType.GOTO, "/home")),
        step("Thấy lời chào", auto(AutoType.SEE_TEXT, "Xin chào")),
    )

    logged_in = make_session(browser, site, tmp_path, storage_state=state).run(case)
    anonymous = make_session(browser, site, tmp_path).run(case)

    assert logged_in.status == ResultStatus.PASS
    assert anonymous.status == ResultStatus.FAIL  # chưa đăng nhập thì bị đưa về /login


def test_login_failure_raises_login_error_without_password(browser: Browser, site: str) -> None:
    config = make_config(site)
    config.login_steps[2] = auto(AutoType.FILL, "{password}", TargetBy.LABEL, "Ô không có")

    with pytest.raises(LoginError) as error:
        perform_login(browser, config, step_timeout_ms=500)

    assert "Đăng nhập" in str(error.value)
    assert PASSWORD not in str(error.value)

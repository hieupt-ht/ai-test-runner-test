"""Test các hàm thuần tính số liệu (không cần Sheets): dựng `ProjectFacts` bằng tay."""

from datetime import UTC, date, datetime

from app.core.models.run import ResultStatus
from app.core.models.stats import BugEvent, CaseFact, ProjectFacts, ResultFact
from app.core.models.test_case import TestCaseStatus
from app.core.services.stats import bug_events, vn_day


def at(text: str) -> datetime:
    """`at("2026-11-19T09:00")` -> thời điểm UTC."""
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def case(
    case_id: str = "TC-1",
    *,
    status: TestCaseStatus = TestCaseStatus.APPROVED,
    created_by: str = "minh@x.com",
    screen_id: str = "SC-1",
    created_at: str = "2026-11-10T01:00",
) -> CaseFact:
    return CaseFact(
        id=case_id,
        screen_id=screen_id,
        status=status,
        created_by=created_by,
        created_at=at(created_at),
    )


def result(
    case_id: str = "TC-1",
    status: ResultStatus = ResultStatus.FAIL,
    when: str = "2026-11-19T09:00",
    by: str = "lan@x.com",
    version: int | None = 1,
) -> ResultFact:
    return ResultFact(
        case_id=case_id,
        status=status,
        created_at=at(when),
        executed_by=by,
        case_version=version,
    )


def test_fail_by_person_credits_runner() -> None:
    facts = ProjectFacts(cases=[case()], results=[result(by="lan@x.com")])
    assert bug_events(facts) == [BugEvent("lan@x.com", "TC-1", date(2026, 11, 19))]


def test_fail_by_agent_credits_case_author() -> None:
    facts = ProjectFacts(
        cases=[case(created_by="minh@x.com")], results=[result(by="codex-windows")]
    )
    assert [event.email for event in bug_events(facts)] == ["minh@x.com"]


def test_many_fails_same_version_count_once_for_first_fail() -> None:
    facts = ProjectFacts(
        cases=[case()],
        results=[
            result(version=2, when="2026-11-19T11:00", by="lan@x.com"),
            result(version=2, when="2026-11-19T09:00", by="lan@x.com"),
            result("TC-1", ResultStatus.PASS, "2026-11-19T09:30"),
            result(version=2, when="2026-11-19T10:00", by="minh@x.com"),
        ],
    )
    events = bug_events(facts)
    assert events == [BugEvent("lan@x.com", "TC-1", date(2026, 11, 19))]


def test_new_version_fail_counts_again() -> None:
    facts = ProjectFacts(
        cases=[case()],
        results=[result(version=1), result(version=2, when="2026-11-20T09:00")],
    )
    assert len(bug_events(facts)) == 2


def test_missing_version_is_one_group() -> None:
    facts = ProjectFacts(
        cases=[case()],
        results=[result(version=None), result(version=None, when="2026-11-19T10:00")],
    )
    assert len(bug_events(facts)) == 1


def test_blocked_and_inconclusive_are_ignored() -> None:
    facts = ProjectFacts(
        cases=[case()],
        results=[result(status=ResultStatus.BLOCKED), result(status=ResultStatus.INCONCLUSIVE)],
    )
    assert bug_events(facts) == []


def test_agent_fail_for_deleted_case_is_skipped() -> None:
    facts = ProjectFacts(cases=[case("TC-1")], results=[result("TC-9", by="codex-windows")])
    assert bug_events(facts) == []


def test_person_fail_for_unknown_case_still_counts_for_runner() -> None:
    # Người chạy tay vẫn được tính dù case không còn trong danh sách
    facts = ProjectFacts(cases=[], results=[result("TC-9", by="lan@x.com")])
    assert [event.email for event in bug_events(facts)] == ["lan@x.com"]


def test_vietnam_day_boundary() -> None:
    assert vn_day(at("2026-11-18T17:30")) == date(2026, 11, 19)
    facts = ProjectFacts(cases=[case()], results=[result(when="2026-11-18T17:30")])
    assert bug_events(facts)[0].day == date(2026, 11, 19)

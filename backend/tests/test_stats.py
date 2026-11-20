"""Test các hàm thuần tính số liệu (không cần Sheets): dựng `ProjectFacts` bằng tay."""

from datetime import UTC, date, datetime

from app.core.models.run import ResultStatus
from app.core.models.stats import BugEvent, CaseFact, PetMood, ProjectFacts, ResultFact
from app.core.models.test_case import TestCaseStatus
from app.core.services.stats import (
    bug_events,
    build_pet,
    level_for,
    mood_for,
    streak_and_missed,
    vn_day,
    work_days,
)


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


# ---- Task 4: ngày làm việc, chuỗi, biểu cảm, cấp nhím ----

MONDAY = date(2026, 11, 23)  # "hôm nay" trong các test chuỗi


def days(*numbers: int) -> set[date]:
    """Các ngày trong tháng 11/2026."""
    return {date(2026, 11, number) for number in numbers}


def test_friday_work_keeps_streak_on_monday_morning() -> None:
    assert streak_and_missed(days(18, 19, 20), MONDAY) == (3, 0)


def test_weekend_work_adds_to_streak() -> None:
    assert streak_and_missed(days(20, 21, 23), MONDAY) == (3, 0)


def test_missing_one_weekday_breaks_streak() -> None:
    streak, _ = streak_and_missed(days(18, 20), MONDAY)
    assert streak == 1


def test_missed_days_count_only_past_weekdays() -> None:
    # Làm lần cuối thứ 3 (17/11): thiếu thứ 4, 5, 6; cuối tuần và hôm nay không tính
    assert streak_and_missed(days(17), MONDAY) == (0, 3)


def test_never_worked_is_zero() -> None:
    assert streak_and_missed(set(), MONDAY) == (0, 0)


def test_level_thresholds() -> None:
    assert level_for(0) == (1, 5)
    assert level_for(4) == (1, 1)
    assert level_for(5) == (2, 15)
    assert level_for(19) == (2, 1)
    assert level_for(20) == (3, 30)
    assert level_for(50) == (4, None)


def test_mood_rules() -> None:
    assert mood_for(caught_bug_today=True, worked_today=True, missed_days=5) == PetMood.HAPPY
    assert mood_for(caught_bug_today=False, worked_today=True, missed_days=0) == PetMood.NORMAL
    assert mood_for(caught_bug_today=False, worked_today=False, missed_days=0) == PetMood.NORMAL
    assert mood_for(caught_bug_today=False, worked_today=False, missed_days=2) == PetMood.HUNGRY
    assert mood_for(caught_bug_today=False, worked_today=False, missed_days=3) == PetMood.CRY


def test_work_days_match_email_ignoring_case() -> None:
    facts = facts_for_pet()
    assert work_days([facts], "AN@x.com") == {date(2026, 11, 10), date(2026, 11, 12)}


def facts_for_pet() -> ProjectFacts:
    """An tạo case ngày 10/11 và chạy một kết quả ngày 12/11; Bình tạo case ngày 11/11."""
    return ProjectFacts(
        cases=[
            case("TC-1", created_by="an@x.com", created_at="2026-11-10T03:00"),
            case("TC-2", created_by="binh@x.com", created_at="2026-11-11T03:00"),
        ],
        results=[result("TC-2", ResultStatus.PASS, "2026-11-12T03:00", by="an@x.com")],
    )


def test_build_pet_sums_bugs_across_projects() -> None:
    def three_bugs() -> ProjectFacts:
        return ProjectFacts(
            cases=[case(f"TC-{n}") for n in range(3)],
            results=[result(f"TC-{n}", when="2026-11-20T03:00", by="an@x.com") for n in range(3)],
        )

    pet = build_pet([three_bugs(), three_bugs()], "AN@x.com", MONDAY)
    assert (pet.bugs, pet.level, pet.bugs_to_next) == (6, 2, 14)
    assert pet.streak == 1  # làm thứ 6, hôm nay (thứ 2) chưa làm vẫn giữ chuỗi
    assert pet.missed_days == 0
    assert pet.mood == PetMood.NORMAL


def test_build_pet_is_happy_when_bug_caught_today() -> None:
    facts = ProjectFacts(
        cases=[case("TC-1")], results=[result("TC-1", when="2026-11-23T03:00", by="an@x.com")]
    )
    pet = build_pet([facts], "an@x.com", MONDAY)
    assert (pet.mood, pet.streak) == (PetMood.HAPPY, 1)

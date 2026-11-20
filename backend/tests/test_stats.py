"""Test các hàm thuần tính số liệu (không cần Sheets): dựng `ProjectFacts` bằng tay."""

from datetime import UTC, date, datetime

from app.core.models.run import ResultStatus
from app.core.models.stats import (
    BugEvent,
    CaseFact,
    DayCount,
    LeaderboardRow,
    Period,
    PetMood,
    ProjectFacts,
    ResultFact,
    ScreenProgress,
)
from app.core.models.test_case import TestCaseStatus
from app.core.services.stats import (
    bug_events,
    build_pet,
    daily_counts,
    leaderboard,
    level_for,
    mood_for,
    period_start,
    progress,
    project_stats,
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


# ---- Task 5: số liệu project, đồ thị ngày, xếp hạng ----

THURSDAY = date(2026, 11, 19)  # "hôm nay" trong các test này


def test_empty_project_stats() -> None:
    stats = project_stats(ProjectFacts(cases=[], results=[]), {}, THURSDAY)
    assert stats.total_cases == 0
    assert stats.pass_rate is None
    assert stats.open_bugs == 0
    assert len(stats.daily) == 14
    assert stats.case_status == {
        TestCaseStatus.DRAFT: 0,
        TestCaseStatus.IN_REVIEW: 0,
        TestCaseStatus.APPROVED: 0,
        TestCaseStatus.TESTED: 0,
    }
    assert stats.screens == []


def test_pass_rate_and_open_bugs_use_latest_pass_fail() -> None:
    P, F, B = ResultStatus.PASS, ResultStatus.FAIL, ResultStatus.BLOCKED
    facts = ProjectFacts(
        cases=[
            case("A"),
            case("B"),
            case("C"),
            case("D", status=TestCaseStatus.ARCHIVED),
        ],
        results=[
            result("A", F, "2026-11-17T01:00"),
            result("A", P, "2026-11-18T01:00"),
            result("B", P, "2026-11-17T01:00"),
            result("B", F, "2026-11-18T01:00"),
            result("B", B, "2026-11-19T01:00"),
            result("C", B, "2026-11-19T01:00"),
            result("D", F, "2026-11-19T01:00"),
        ],
    )
    stats = project_stats(facts, {}, THURSDAY)
    assert stats.pass_rate == 0.5
    assert stats.open_bugs == 1


def test_results_of_unknown_case_are_ignored() -> None:
    facts = ProjectFacts(
        cases=[case("A")],
        results=[result("A", ResultStatus.PASS, "2026-11-19T01:00"), result("TC-X")],
    )
    stats = project_stats(facts, {}, THURSDAY)
    assert stats.pass_rate == 1.0
    assert stats.open_bugs == 0
    # Đồ thị đếm mọi lần chạy, kể cả của case không còn trong danh sách
    assert stats.daily[-1] == DayCount(day=THURSDAY, passed=1, failed=1, other=0)


def test_daily_counts_buckets_by_vietnam_day() -> None:
    facts = ProjectFacts(
        cases=[case()],
        results=[
            result(status=ResultStatus.PASS, when="2026-11-18T17:30"),  # 00:30 ngày 19 giờ VN
            result(status=ResultStatus.BLOCKED, when="2026-11-19T01:00"),
            result(status=ResultStatus.INCONCLUSIVE, when="2026-11-19T02:00"),
        ],
    )
    rows = daily_counts([facts], THURSDAY, days=3)
    assert [row.day for row in rows] == [date(2026, 11, 17), date(2026, 11, 18), THURSDAY]
    assert rows[1] == DayCount(day=date(2026, 11, 18), passed=0, failed=0, other=0)
    assert rows[2] == DayCount(day=THURSDAY, passed=1, failed=0, other=2)


def test_screen_progress_counts_done_over_total() -> None:
    facts = ProjectFacts(
        cases=[
            case("1", status=TestCaseStatus.DRAFT),
            case("2", status=TestCaseStatus.APPROVED),
            case("3", status=TestCaseStatus.TESTED),
            case("4", status=TestCaseStatus.DEPRECATED),
        ],
        results=[],
    )
    assert progress(facts) == (2, 3)
    stats = project_stats(facts, {"SC-1": "Đăng nhập", "SC-2": "Giỏ hàng"}, THURSDAY)
    assert stats.screens == [
        ScreenProgress(screen_id="SC-1", screen_name="Đăng nhập", done=2, total=3),
        ScreenProgress(screen_id="SC-2", screen_name="Giỏ hàng", done=0, total=0),
    ]


def test_period_start() -> None:
    assert period_start(Period.WEEK, THURSDAY) == date(2026, 11, 16)
    assert period_start(Period.MONTH, THURSDAY) == date(2026, 11, 1)
    assert period_start(Period.ALL, THURSDAY) is None


NAMES = {"an@x.com": "An", "binh@x.com": "Bình"}


def row(rank: int | None, email: str, name: str, count: int) -> LeaderboardRow:
    return LeaderboardRow(rank=rank, email=email, name=name, count=count)


def test_leaderboard_cases_counts_approved_and_tested_by_author() -> None:
    facts = ProjectFacts(
        cases=[
            case("1", created_by="an@x.com"),
            case("2", created_by="an@x.com"),
            case("3", created_by="an@x.com", status=TestCaseStatus.DRAFT),
            case("4", created_by="binh@x.com", status=TestCaseStatus.TESTED),
        ],
        results=[],
    )
    board = leaderboard(facts, NAMES, Period.ALL, THURSDAY, me="an@x.com").cases
    assert board.top == [row(1, "an@x.com", "An", 2), row(2, "binh@x.com", "Bình", 1)]
    assert board.me is None


def bugs_for(*people: tuple[str, int]) -> ProjectFacts:
    """Mỗi người bắt `n` bug (mỗi bug một case riêng) vào ngày 19/11."""
    cases: list[CaseFact] = []
    results: list[ResultFact] = []
    for email, count in people:
        for number in range(count):
            case_id = f"{email}-{number}"
            cases.append(case(case_id))
            results.append(result(case_id, by=email))
    return ProjectFacts(cases=cases, results=results)


def test_leaderboard_ties_share_rank() -> None:
    facts = bugs_for(("an@x.com", 3), ("binh@x.com", 3), ("cuong@x.com", 1))
    top = leaderboard(facts, NAMES, Period.ALL, THURSDAY, me="an@x.com").bugs.top
    assert [(r.rank, r.email) for r in top] == [
        (1, "an@x.com"),
        (1, "binh@x.com"),
        (3, "cuong@x.com"),
    ]
    assert top[2].name == "cuong@x.com"  # thiếu tên thì dùng email


def test_leaderboard_me_outside_top() -> None:
    people = [(f"p{n}@x.com", 10 - n) for n in range(6)]  # p5 có 5 bug, hạng 6
    facts = bugs_for(*people)
    board = leaderboard(facts, {}, Period.ALL, THURSDAY, me="p5@x.com").bugs
    assert len(board.top) == 5
    assert board.me == row(6, "p5@x.com", "p5@x.com", 5)

    nobody = leaderboard(facts, {}, Period.ALL, THURSDAY, me="moi@x.com").bugs
    assert nobody.me == row(None, "moi@x.com", "moi@x.com", 0)

    in_top = leaderboard(facts, {}, Period.ALL, THURSDAY, me="p0@x.com").bugs
    assert in_top.me is None


def test_leaderboard_week_filter() -> None:
    facts = ProjectFacts(
        cases=[case("1"), case("2")],
        results=[
            result("1", when="2026-11-15T03:00", by="an@x.com"),  # Chủ nhật tuần trước
            result("2", when="2026-11-16T03:00", by="binh@x.com"),  # thứ 2 tuần này
        ],
    )
    week = leaderboard(facts, NAMES, Period.WEEK, THURSDAY, me="an@x.com").bugs
    assert [r.email for r in week.top] == ["binh@x.com"]
    month = leaderboard(facts, NAMES, Period.MONTH, THURSDAY, me="an@x.com").bugs
    assert [r.email for r in month.top] == ["an@x.com", "binh@x.com"]

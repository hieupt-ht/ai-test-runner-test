"""Các hàm thuần tính số liệu từ `ProjectFacts` (không đụng Sheets hay Redis).

Mọi hàm nhận `today` từ ngoài vào nên test được và không phụ thuộc giờ của cache.
"""

from datetime import date, datetime, timedelta

from app.core.models.run import Result, ResultStatus
from app.core.models.stats import (
    Board,
    BugEvent,
    CaseFact,
    DayCount,
    Leaderboard,
    LeaderboardRow,
    MyPet,
    Period,
    PetMood,
    ProjectFacts,
    ProjectStats,
    ResultFact,
    ScreenProgress,
)
from app.core.models.test_case import TestCase, TestCaseStatus
from app.core.models.user import normalize_email
from app.core.time import VIETNAM


def _email_or_raw(value: str) -> str:
    """Chuẩn hoá email; tên agent (không có "@") giữ nguyên."""
    return normalize_email(value) if "@" in value else value


def facts_from(cases: list[TestCase], results: list[Result]) -> ProjectFacts:
    """Rút gọn case và kết quả đầy đủ thành bản tóm tắt nhỏ để cache."""
    return ProjectFacts(
        cases=[
            CaseFact(
                id=case.id,
                screen_id=case.screen_id,
                status=case.status,
                created_by=_email_or_raw(case.created_by),
                created_at=case.created_at,
            )
            for case in cases
        ],
        results=[
            ResultFact(
                case_id=result.test_case_id,
                status=result.status,
                created_at=result.created_at,
                executed_by=_email_or_raw(result.executed_by),
                case_version=result.case_version,
            )
            for result in results
        ],
    )


def vn_day(moment: datetime) -> date:
    """Ngày của một thời điểm theo giờ Việt Nam (23:30 UTC đã là sáng hôm sau ở Việt Nam)."""
    return moment.astimezone(VIETNAM).date()


def bug_events(facts: ProjectFacts) -> list[BugEvent]:
    """Mỗi (case, phiên bản case) có FAIL chỉ tính 1 bug, cho người FAIL đầu tiên.

    Người được tính: người chạy tay (executed_by có "@"), còn agent thì tính cho tác giả case.
    """
    author_of = {case.id: case.created_by for case in facts.cases}
    first_fail: dict[tuple[str, int | None], ResultFact] = {}
    for item in facts.results:
        if item.status != ResultStatus.FAIL:
            continue
        key = (item.case_id, item.case_version)
        if key not in first_fail or item.created_at < first_fail[key].created_at:
            first_fail[key] = item

    events: list[BugEvent] = []
    for item in first_fail.values():
        if "@" in item.executed_by:
            email = item.executed_by
        elif item.case_id in author_of:
            email = author_of[item.case_id]
        else:
            continue  # agent báo FAIL cho case đã bị xoá: không biết tính cho ai
        events.append(BugEvent(email, item.case_id, vn_day(item.created_at)))
    return sorted(events, key=lambda event: (event.day, event.case_id, event.email))


# ---- Nhím: ngày làm việc, chuỗi, cấp, biểu cảm ----

# Số bug cần có để vào cấp 1, 2, 3, 4
LEVEL_THRESHOLDS = [0, 5, 20, 50]


def work_days(facts_list: list[ProjectFacts], email: str) -> set[date]:
    """Các ngày (giờ VN) người này có tạo case hoặc chạy kết quả, ở mọi project.

    Kết quả do agent chạy không tính là ngày làm việc của tác giả case.
    """
    wanted = normalize_email(email)
    days: set[date] = set()
    for facts in facts_list:
        days.update(vn_day(case.created_at) for case in facts.cases if case.created_by == wanted)
        days.update(vn_day(item.created_at) for item in facts.results if item.executed_by == wanted)
    return days


def _is_weekday(day: date) -> bool:
    return day.weekday() < 5  # thứ 2 = 0 ... thứ 6 = 4


def streak_and_missed(days: set[date], today: date) -> tuple[int, int]:
    """(chuỗi ngày liên tiếp, số ngày làm việc đã bỏ lỡ gần đây).

    Chuỗi đi lùi từ hôm nay: hôm nay chưa làm và cuối tuần không làm thì không đứt chuỗi;
    một ngày thứ 2-6 trong quá khứ mà không làm thì chuỗi dừng.
    """
    past = {day for day in days if day <= today}
    if not past:
        return (0, 0)

    streak = 0
    day = today
    while day >= min(past):
        if day in past:
            streak += 1
        elif day != today and _is_weekday(day):
            break
        day -= timedelta(days=1)

    last = max(past)
    missed = 0
    day = last + timedelta(days=1)
    while day < today:
        if _is_weekday(day):
            missed += 1
        day += timedelta(days=1)
    return (streak, missed)


def level_for(bugs: int) -> tuple[int, int | None]:
    """(cấp nhím, số bug còn thiếu để lên cấp tiếp; cấp cao nhất thì None)."""
    level = sum(bugs >= threshold for threshold in LEVEL_THRESHOLDS)
    if level == len(LEVEL_THRESHOLDS):
        return (level, None)
    return (level, LEVEL_THRESHOLDS[level] - bugs)


def mood_for(*, caught_bug_today: bool, worked_today: bool, missed_days: int) -> PetMood:
    if caught_bug_today:
        return PetMood.HAPPY
    if worked_today or missed_days == 0:
        return PetMood.NORMAL
    return PetMood.HUNGRY if missed_days <= 2 else PetMood.CRY


def build_pet(facts_list: list[ProjectFacts], email: str, today: date) -> MyPet:
    wanted = normalize_email(email)
    events = [event for facts in facts_list for event in bug_events(facts) if event.email == wanted]
    days = work_days(facts_list, wanted)
    streak, missed = streak_and_missed(days, today)
    level, to_next = level_for(len(events))
    return MyPet(
        level=level,
        bugs=len(events),
        bugs_to_next=to_next,
        streak=streak,
        missed_days=missed,
        mood=mood_for(
            caught_bug_today=any(event.day == today for event in events),
            worked_today=today in days,
            missed_days=missed,
        ),
    )


# ---- Số liệu project ----

# Case đã lưu trữ hoặc ngừng dùng không tính vào số liệu
_INACTIVE = {TestCaseStatus.ARCHIVED, TestCaseStatus.DEPRECATED}
_DONE = {TestCaseStatus.APPROVED, TestCaseStatus.TESTED}
_SHOWN_STATUSES = [
    TestCaseStatus.DRAFT,
    TestCaseStatus.IN_REVIEW,
    TestCaseStatus.APPROVED,
    TestCaseStatus.TESTED,
]


def daily_counts(facts_list: list[ProjectFacts], today: date, days: int = 14) -> list[DayCount]:
    """Số lần chạy mỗi ngày trong `days` ngày kết thúc ở `today`; mỗi dòng kết quả đếm một lần."""
    first = today - timedelta(days=days - 1)
    counts = {first + timedelta(days=offset): [0, 0, 0] for offset in range(days)}
    for facts in facts_list:
        for item in facts.results:
            bucket = counts.get(vn_day(item.created_at))
            if bucket is None:
                continue  # ngoài khoảng đồ thị
            if item.status == ResultStatus.PASS:
                bucket[0] += 1
            elif item.status == ResultStatus.FAIL:
                bucket[1] += 1
            else:
                bucket[2] += 1
    return [DayCount(day=day, passed=p, failed=f, other=o) for day, (p, f, o) in counts.items()]


def progress(facts: ProjectFacts) -> tuple[int, int]:
    """(số case đã duyệt hoặc đã test, tổng số case còn dùng)."""
    active = [case for case in facts.cases if case.status not in _INACTIVE]
    return (sum(case.status in _DONE for case in active), len(active))


def _latest_pass_fail(facts: ProjectFacts) -> dict[str, ResultStatus]:
    """Kết quả PASS/FAIL mới nhất của mỗi case còn dùng (bỏ qua case lạ hoặc đã lưu trữ)."""
    active = {case.id for case in facts.cases if case.status not in _INACTIVE}
    latest: dict[str, ResultFact] = {}
    for item in facts.results:
        if item.case_id not in active or item.status not in {ResultStatus.PASS, ResultStatus.FAIL}:
            continue
        if item.case_id not in latest or item.created_at >= latest[item.case_id].created_at:
            latest[item.case_id] = item
    return {case_id: item.status for case_id, item in latest.items()}


def project_stats(facts: ProjectFacts, screen_names: dict[str, str], today: date) -> ProjectStats:
    latest = _latest_pass_fail(facts)
    passed = sum(status == ResultStatus.PASS for status in latest.values())
    _, total = progress(facts)
    return ProjectStats(
        total_cases=total,
        pass_rate=passed / len(latest) if latest else None,
        open_bugs=len(latest) - passed,
        daily=daily_counts([facts], today),
        case_status={
            status: sum(case.status == status for case in facts.cases) for status in _SHOWN_STATUSES
        },
        screens=[
            ScreenProgress(
                screen_id=screen_id,
                screen_name=name,
                done=sum(
                    case.screen_id == screen_id and case.status in _DONE for case in facts.cases
                ),
                total=sum(
                    case.screen_id == screen_id and case.status not in _INACTIVE
                    for case in facts.cases
                ),
            )
            for screen_id, name in screen_names.items()
        ],
    )


# ---- Bảng xếp hạng ----


def period_start(period: Period, today: date) -> date | None:
    """Ngày đầu của kỳ: tuần bắt đầu từ thứ 2, tháng từ ngày 1, "tất cả" thì không giới hạn."""
    if period == Period.WEEK:
        return today - timedelta(days=today.weekday())
    if period == Period.MONTH:
        return today.replace(day=1)
    return None


def _board(counts: dict[str, int], names: dict[str, str], me: str, top: int) -> Board:
    def name_of(email: str) -> str:
        return names.get(email) or email

    ordered = sorted(
        ((email, count) for email, count in counts.items() if count > 0),
        key=lambda item: (-item[1], name_of(item[0]), item[0]),
    )
    rows: list[LeaderboardRow] = []
    for index, (email, count) in enumerate(ordered):
        # Bằng điểm thì chung hạng (1, 1, 3): lấy hạng của người đứng ngay trước nếu cùng điểm
        rank = rows[-1].rank if rows and rows[-1].count == count else index + 1
        rows.append(LeaderboardRow(rank=rank, email=email, name=name_of(email), count=count))

    my_row = next((row for row in rows if row.email == me), None)
    if my_row is None:
        my_row = LeaderboardRow(rank=None, email=me, name=name_of(me), count=0)
    return Board(top=rows[:top], me=None if my_row in rows[:top] else my_row)


def leaderboard(
    facts: ProjectFacts,
    names: dict[str, str],
    period: Period,
    today: date,
    me: str,
    top: int = 5,
) -> Leaderboard:
    """Xếp hạng người viết case (đã duyệt/đã test) và người bắt bug của một project."""
    me = normalize_email(me)
    start = period_start(period, today)

    case_counts: dict[str, int] = {}
    for case in facts.cases:
        if case.status in _DONE and (start is None or vn_day(case.created_at) >= start):
            case_counts[case.created_by] = case_counts.get(case.created_by, 0) + 1

    bug_counts: dict[str, int] = {}
    for event in bug_events(facts):
        if start is None or event.day >= start:
            bug_counts[event.email] = bug_counts.get(event.email, 0) + 1

    return Leaderboard(
        period=period,
        cases=_board(case_counts, names, me, top),
        bugs=_board(bug_counts, names, me, top),
    )

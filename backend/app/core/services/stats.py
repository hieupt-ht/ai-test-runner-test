"""Các hàm thuần tính số liệu từ `ProjectFacts` (không đụng Sheets hay Redis).

Mọi hàm nhận `today` từ ngoài vào nên test được và không phụ thuộc giờ của cache.
"""

from datetime import date, datetime, timedelta

from app.core.models.run import Result, ResultStatus
from app.core.models.stats import (
    BugEvent,
    CaseFact,
    MyPet,
    PetMood,
    ProjectFacts,
    ResultFact,
)
from app.core.models.test_case import TestCase
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

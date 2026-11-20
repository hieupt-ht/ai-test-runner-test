"""Các hàm thuần tính số liệu từ `ProjectFacts` (không đụng Sheets hay Redis).

Mọi hàm nhận `today` từ ngoài vào nên test được và không phụ thuộc giờ của cache.
"""

from datetime import date, datetime

from app.core.models.run import Result, ResultStatus
from app.core.models.stats import BugEvent, CaseFact, ProjectFacts, ResultFact
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

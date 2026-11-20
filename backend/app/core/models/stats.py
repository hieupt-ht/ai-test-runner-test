"""Model cho số liệu: bản tóm tắt dữ liệu gốc của project và các kết quả tính ra từ nó."""

from dataclasses import dataclass
from datetime import date, datetime

from pydantic import BaseModel

from app.core.models.run import ResultStatus
from app.core.models.test_case import TestCaseStatus


class CaseFact(BaseModel):
    """Phần của test case mà số liệu cần (đủ nhỏ để lưu cache)."""

    id: str
    screen_id: str
    status: TestCaseStatus
    created_by: str
    created_at: datetime


class ResultFact(BaseModel):
    """Phần của một kết quả chạy mà số liệu cần."""

    case_id: str
    status: ResultStatus
    created_at: datetime
    executed_by: str
    case_version: int | None


class ProjectFacts(BaseModel):
    """Dữ liệu gốc của một project. Mọi con số đều tính từ đây bằng hàm thuần."""

    cases: list[CaseFact]
    results: list[ResultFact]


@dataclass(frozen=True)
class BugEvent:
    """Một lần "bắt được bug": ai bắt, ở case nào, vào ngày nào (giờ Việt Nam)."""

    email: str
    case_id: str
    day: date

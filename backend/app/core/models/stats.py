"""Model cho số liệu: bản tóm tắt dữ liệu gốc của project và các kết quả tính ra từ nó."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

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


class PetMood(StrEnum):
    HAPPY = "HAPPY"  # hôm nay vừa bắt được bug
    NORMAL = "NORMAL"
    HUNGRY = "HUNGRY"  # vắng 1-2 ngày làm việc
    CRY = "CRY"  # vắng từ 3 ngày làm việc


class MyPet(BaseModel):
    """Con nhím của một người: cấp theo số bug, biểu cảm theo chuỗi ngày."""

    level: int  # 1..4
    bugs: int
    bugs_to_next: int | None  # số bug còn thiếu để lên cấp; cấp cao nhất thì None
    streak: int
    missed_days: int
    mood: PetMood


class DayCount(BaseModel):
    """Số lần chạy trong một ngày (giờ VN) cho đồ thị cột."""

    day: date
    passed: int
    failed: int
    other: int  # BLOCKED + INCONCLUSIVE


class ScreenProgress(BaseModel):
    screen_id: str
    screen_name: str
    done: int  # case APPROVED hoặc TESTED
    total: int  # case chưa lưu trữ / ngừng dùng


class ProjectStats(BaseModel):
    """Các con số của trang Tổng quan project."""

    total_cases: int
    pass_rate: float | None  # None khi chưa có case nào được chạy PASS/FAIL
    open_bugs: int
    daily: list[DayCount]
    case_status: dict[TestCaseStatus, int]  # luôn đủ DRAFT, IN_REVIEW, APPROVED, TESTED
    screens: list[ScreenProgress]


class Period(StrEnum):
    WEEK = "week"
    MONTH = "month"
    ALL = "all"


class LeaderboardRow(BaseModel):
    rank: int | None  # None: người xem chưa có điểm nào
    email: str
    name: str
    count: int


class Board(BaseModel):
    top: list[LeaderboardRow]
    me: LeaderboardRow | None  # chỉ có khi người xem nằm ngoài top


class Leaderboard(BaseModel):
    period: Period
    cases: Board  # xếp hạng viết case
    bugs: Board  # xếp hạng bắt bug


class ProjectProgress(BaseModel):
    """Tiến độ case của một project (cho biểu đồ ở Tổng quan chung)."""

    project_id: str
    project_name: str
    done: int
    total: int


class MyDashboard(BaseModel):
    projects: list[ProjectProgress]
    daily: list[DayCount]  # số lần chạy 14 ngày qua, cộng dồn mọi project của tôi

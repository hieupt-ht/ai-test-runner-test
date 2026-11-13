from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.models.test_case import TestCaseStatus


class AssignmentStatus(StrEnum):
    # Ở M2 luôn là TODO. Từ M3, trạng thái tự suy ra từ các test case của màn hình.
    TODO = "TODO"
    WRITING = "WRITING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    TESTED = "TESTED"


class Assignment(BaseModel):
    id: str
    screen_id: str
    assignee_email: str
    deadline: date
    status: AssignmentStatus
    updated_at: datetime


class MyAssignment(BaseModel):
    """Một dòng trong trang "Việc của tôi"."""

    assignment_id: str
    project_id: str
    project_name: str
    screen_id: str
    screen_name: str
    deadline: date
    status: AssignmentStatus
    # Số case của chính user trên màn hình này, theo từng trạng thái (đủ 4 khoá).
    case_counts: dict[TestCaseStatus, int] = Field(
        default_factory=lambda: {status: 0 for status in TestCaseStatus}
    )

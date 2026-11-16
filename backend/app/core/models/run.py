from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.models.test_case import Priority, Severity


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ACTIVE_RUN_STATUSES = {RunStatus.QUEUED, RunStatus.RUNNING}


class ResultStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    INCONCLUSIVE = "INCONCLUSIVE"


class RunScope(BaseModel):
    """Phạm vi một lần chạy. Danh sách rỗng nghĩa là "không lọc theo tiêu chí này"."""

    screen_ids: list[str] = Field(default_factory=list)
    priorities: list[Priority] = Field(default_factory=list)
    severities: list[Severity] = Field(default_factory=list)


class Run(BaseModel):
    id: str
    triggered_by: str
    scope: RunScope
    branch: str
    commit_sha: str  # M4 chưa dùng, để rỗng
    status: RunStatus
    started_at: datetime  # lúc tạo run
    finished_at: datetime | None
    total: int
    passed: int
    failed: int
    tokens_used: int  # M4 không dùng AI nên luôn 0


class Result(BaseModel):
    id: str  # "<run_id>-<test_case_id>"
    run_id: str
    test_case_id: str
    status: ResultStatus
    reason: str
    failed_step: int | None  # đánh số từ 1
    # Đường dẫn tương đối trong thư mục artifacts, ví dụ "RUN-0001/TC-000002.png"
    screenshot: str | None
    created_at: datetime

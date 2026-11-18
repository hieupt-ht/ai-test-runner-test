from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.core.models.media import Media
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
    # Run regression: chỉ chạy các case regression, ghi rõ danh sách case của lần chạy này
    regression_only: bool = False
    case_ids: list[str] = Field(default_factory=list)


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
    build_version: str = ""  # bản build được test, ví dụ "1.4.2"


class Evidence(BaseModel):
    """Bằng chứng của một kết quả: video cả lần chạy và ảnh các bước."""

    video: Media | None = None
    screenshots: list[Media] = Field(default_factory=list, max_length=20)
    # Link https do bản cũ lưu (một chuỗi duy nhất); không phải file của mình nên không bị dọn
    legacy_url: str | None = None
    # Bằng chứng đã bị dọn để tiết kiệm chỗ (chỉ giữ 5 lần chạy gần nhất mỗi case)
    pruned: bool = False


class StepResult(BaseModel):
    """Kết quả của riêng một bước trong case."""

    step_no: int = Field(ge=1)
    status: Literal["PASS", "FAIL", "SKIPPED"]
    actual: str = Field(default="", max_length=1000)
    screenshot: Media | None = None


class Result(BaseModel):
    id: str  # "<run_id>-<test_case_id>"
    run_id: str
    test_case_id: str
    status: ResultStatus
    reason: str
    failed_step: int | None  # đánh số từ 1
    created_at: datetime
    evidence: Evidence = Field(default_factory=Evidence)
    step_results: list[StepResult] = Field(default_factory=list)
    actual_result: str = ""
    environment: str = ""  # ví dụ "Pixel 7 / Android 14"
    executed_by: str = ""  # ví dụ "codex-windows"
    case_version: int | None = None  # phiên bản case lúc chạy
    dev_owner: str = ""  # dev phụ trách màn hình lúc ghi kết quả
    defect_url: str = ""

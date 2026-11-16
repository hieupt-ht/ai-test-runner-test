from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TestCaseStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    TESTED = "TESTED"
    ARCHIVED = "ARCHIVED"
    DEPRECATED = "DEPRECATED"


class TestStep(BaseModel):
    """Một bước kiểm thử: làm gì và kết quả mong đợi (được để trống)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: str = Field(min_length=1, max_length=500)
    expected: str = Field(default="", max_length=500)


class TestCaseContent(BaseModel):
    """Phần nội dung do người dùng nhập khi tạo hoặc sửa test case."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    precondition: str = Field(default="", max_length=2000)
    test_data: str = Field(default="", max_length=2000)
    steps: list[TestStep] = Field(min_length=1, max_length=50)
    expected_result: str = Field(min_length=1, max_length=2000)
    severity: Severity
    priority: Priority


class TestCase(TestCaseContent):
    """Một test case đầy đủ, như lưu ở tab TestCases."""

    id: str
    screen_id: str
    status: TestCaseStatus
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
    version: int

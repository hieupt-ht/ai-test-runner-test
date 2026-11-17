from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.core.models.media import Media, MediaList


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


class Platform(StrEnum):
    WEB = "WEB"
    ANDROID = "ANDROID"
    IOS = "IOS"


class TestType(StrEnum):
    FUNCTIONAL = "FUNCTIONAL"  # kiểm tra chức năng
    UI = "UI"  # kiểm tra giao diện


class TestStep(BaseModel):
    """Một bước kiểm thử: làm gì và kết quả mong đợi (được để trống)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: str = Field(min_length=1, max_length=500)
    expected: str = Field(default="", max_length=500)
    guide_media: MediaList = Field(default_factory=list)  # ảnh/video chỉ đường cho bước này


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
    platform: Platform = Platform.WEB
    test_type: TestType = TestType.FUNCTIONAL
    regression: bool = False  # True: thuộc bộ regression
    start_point: str = Field(default="", max_length=500)  # điểm bắt đầu (màn hình/đường dẫn)
    guide_media: MediaList = Field(default_factory=list)  # ảnh/video chỉ đường cho cả case
    postcondition: str = Field(default="", max_length=2000)
    requirement_ref: str = Field(default="", max_length=200)


# Tên tiếng Việt của từng trường nội dung, dùng khi báo "đã sửa gì" trên issue và lịch sử
CHANGED_FIELD_LABELS: dict[str, str] = {
    "title": "Tiêu đề",
    "precondition": "Điều kiện trước",
    "test_data": "Dữ liệu test",
    "steps": "Các bước",
    "expected_result": "Kết quả mong đợi",
    "severity": "Mức độ nghiêm trọng",
    "priority": "Độ ưu tiên",
    "platform": "Nền tảng",
    "test_type": "Loại test",
    "regression": "Regression",
    "start_point": "Điểm bắt đầu",
    "guide_media": "Ảnh/video hướng dẫn",
    "postcondition": "Điều kiện sau",
    "requirement_ref": "Mã yêu cầu",
}

# Đổi các trường này thì kết quả chạy cũ không còn đúng với case: cần chạy lại.
# (guide_media trong từng bước nằm trong `steps` nên cũng được tính.)
RERUN_FIELDS = {"steps", "expected_result", "start_point", "platform", "guide_media"}


def media_of(case: TestCaseContent) -> list[Media]:
    """Mọi ảnh/video của case (cả case và từng bước), dùng để kiểm tra cloud và dọn file."""
    return [*case.guide_media, *(media for step in case.steps for media in step.guide_media)]


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

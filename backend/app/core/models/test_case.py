from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    DEPRECATED = "DEPRECATED"


class AutoType(StrEnum):
    """Hành động mà worker (Playwright) làm được."""

    GOTO = "goto"  # mở trang
    FILL = "fill"  # nhập chữ
    CLICK = "click"  # bấm
    SELECT = "select"  # chọn trong danh sách
    SEE_TEXT = "see_text"  # kiểm tra chữ CÓ hiện
    NOT_SEE_TEXT = "not_see_text"  # kiểm tra chữ KHÔNG hiện
    URL_IS = "url_is"  # kiểm tra URL


class TargetBy(StrEnum):
    TEXT = "text"  # chữ hiển thị
    LABEL = "label"  # nhãn của ô nhập
    CSS = "css"  # selector CSS (mục "Nâng cao")


# Loại bước cần chỉ ra phần tử; các loại còn lại không có phần tử.
_NEEDS_TARGET = {AutoType.FILL, AutoType.CLICK, AutoType.SELECT}
# Loại bước bắt buộc có giá trị (fill được để trống để xoá ô, click không cần giá trị).
_NEEDS_VALUE = {
    AutoType.GOTO,
    AutoType.SELECT,
    AutoType.SEE_TEXT,
    AutoType.NOT_SEE_TEXT,
    AutoType.URL_IS,
}


class AutoTarget(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    by: TargetBy
    value: str = Field(min_length=1, max_length=500)


class AutoStep(BaseModel):
    """Phần tự động của một bước: worker dựa vào đây để chạy bằng Playwright."""

    model_config = ConfigDict(str_strip_whitespace=True)

    type: AutoType
    target: AutoTarget | None = None
    value: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if self.type in _NEEDS_TARGET and self.target is None:
            raise ValueError(f'Bước "{self.type.value}" cần chọn phần tử')
        if self.type not in _NEEDS_TARGET and self.target is not None:
            raise ValueError(f'Bước "{self.type.value}" không có phần tử')
        if self.type in _NEEDS_VALUE and not self.value:
            raise ValueError(f'Bước "{self.type.value}" cần có giá trị')
        return self


class TestStep(BaseModel):
    """Một bước kiểm thử: làm gì và kết quả mong đợi (được để trống).

    `auto` (tuỳ chọn) là phần để worker chạy tự động; case cũ không có thì để trống.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    action: str = Field(min_length=1, max_length=500)
    expected: str = Field(default="", max_length=500)
    auto: AutoStep | None = None


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

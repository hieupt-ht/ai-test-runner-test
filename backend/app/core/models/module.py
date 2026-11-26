import unicodedata
from datetime import date, datetime

from pydantic import BaseModel


class Module(BaseModel):
    """Một nhóm màn hình (ví dụ "Tài khoản") để QA chia việc cho tester."""

    id: str
    name: str
    description: str
    created_at: datetime


class ModuleAssignment(BaseModel):
    """Ai đang nhận làm module nào, hạn bao giờ."""

    id: str
    module_id: str
    assignee_email: str
    deadline: date
    created_at: datetime


def name_key(name: str) -> str:
    """Khoá so tên (module, màn hình): bỏ khoảng trắng thừa, không phân biệt hoa/thường."""
    return unicodedata.normalize("NFC", name).strip().casefold()

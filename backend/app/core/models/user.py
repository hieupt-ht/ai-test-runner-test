from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    ADMIN = "ADMIN"
    QA_LEAD = "QA_LEAD"
    TESTER = "TESTER"
    VIEWER = "VIEWER"


class User(BaseModel):
    email: str
    name: str
    role: Role
    active: bool
    created_at: datetime


def normalize_email(email: str) -> str:
    """So sánh email không phân biệt hoa/thường và bỏ khoảng trắng thừa."""
    return email.strip().lower()

from datetime import datetime

from pydantic import BaseModel


class Project(BaseModel):
    id: str
    name: str
    repo_full_name: str  # ví dụ "Cross-Players/shop-app"
    branch: str
    staging_url: str  # để sẵn cho giai đoạn 2, có thể rỗng
    spreadsheet_id: str  # file Sheet riêng của dự án
    archived: bool
    created_at: datetime


class ProjectMember(BaseModel):
    project_id: str
    email: str
    added_at: datetime

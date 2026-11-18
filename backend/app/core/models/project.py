from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Nơi lưu ảnh/video của dự án
Storage = Literal["cloudinary", "drive"]


class Project(BaseModel):
    id: str
    name: str
    repo_full_name: str  # ví dụ "Cross-Players/shop-app"
    branch: str
    staging_url: str  # để sẵn cho giai đoạn 2, có thể rỗng
    spreadsheet_id: str  # file Sheet riêng của dự án
    archived: bool
    created_at: datetime
    android_app_id: str = ""  # ví dụ "com.shop.app", dùng khi test Android
    ios_bundle_id: str = ""  # ví dụ "vn.shop.app", dùng khi test iOS
    require_review: bool = False  # False: tester gửi là duyệt luôn, không qua QA Lead
    storage: Storage = "cloudinary"  # nơi lưu ảnh/video; chỉ Admin đổi


class ProjectMember(BaseModel):
    project_id: str
    email: str
    added_at: datetime

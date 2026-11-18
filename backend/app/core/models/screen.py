from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from app.core.models.media import MediaList

MAX_CODE_PATHS = 20


def _check_code_path(path: str) -> str:
    """Đường dẫn tương đối trong repo, ví dụ `src/pages/login.tsx` hoặc `api/auth/`.

    Chặn đường dẫn tuyệt đối và `..` để AI không đọc ra ngoài thư mục repo.
    """
    if path.startswith("/"):
        raise ValueError("Đường dẫn phải là đường dẫn tương đối, không bắt đầu bằng /")
    if "\\" in path:
        raise ValueError("Dùng dấu / thay cho dấu \\")
    if ".." in path.split("/"):
        raise ValueError("Đường dẫn không được chứa ..")
    return path


CodePath = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(_check_code_path),
]


class Screen(BaseModel):
    id: str
    name: str
    description: str
    route: str
    code_paths: list[str]
    created_at: datetime
    dev_owner: str = ""  # tên GitHub của dev phụ trách, dùng để giao bug
    # Ảnh/video tham khảo để tester hình dung màn hình (không đưa lên GitHub issue)
    media: MediaList = Field(default_factory=list)

"""Cấu hình app của từng dự án, đọc từ file `worker-projects.json` trên máy worker.

File này nằm ngoài Sheet và ngoài API (gitignore) vì:
- đường dẫn và lệnh chạy chỉ có ý nghĩa trên máy này;
- không có cách nào sửa lệnh chạy qua web, nên không ai chèn lệnh lạ vào máy được;
- chứa mật khẩu tài khoản test.

Thông báo lỗi tuyệt đối không được in mật khẩu.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.core.models.test_case import AutoStep


class WorkerConfigError(Exception):
    """File cấu hình thiếu hoặc sai. Thông báo nói rõ cần sửa gì."""


class ProjectWorkerConfig(BaseModel):
    app_path: str
    start_command: str
    app_url: str
    test_email: str
    test_password: str
    # Các bước đăng nhập; {email} và {password} được thay bằng tài khoản test.
    login_steps: list[AutoStep] = []


def _describe(error: ValidationError) -> str:
    """Chỉ nêu tên trường và lý do, không kèm giá trị người dùng nhập (có thể là mật khẩu)."""
    parts = [
        f"{'.'.join(str(item) for item in problem['loc'])}: {problem['msg']}"
        for problem in error.errors(include_input=False, include_url=False)
    ]
    return "; ".join(parts)


def load_project_config(path: Path, project_id: str) -> ProjectWorkerConfig:
    if not path.is_file():
        raise WorkerConfigError(
            f"Không thấy file cấu hình {path.name}. "
            "Hãy tạo file này từ worker-projects.example.json."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise WorkerConfigError(
            f"Không đọc được {path.name}: file không phải JSON hợp lệ"
        ) from error

    raw = data.get(project_id) if isinstance(data, dict) else None
    if raw is None:
        raise WorkerConfigError(f"Chưa có cấu hình cho dự án {project_id} trong {path.name}")

    try:
        config = ProjectWorkerConfig.model_validate(raw)
    except ValidationError as error:
        raise WorkerConfigError(
            f"Cấu hình dự án {project_id} trong {path.name} chưa đúng: {_describe(error)}"
        ) from error

    if not Path(config.app_path).is_dir():
        raise WorkerConfigError(
            f"app_path của dự án {project_id} không phải một thư mục có thật: {config.app_path}"
        )
    return config

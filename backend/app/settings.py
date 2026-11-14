"""Đọc cấu hình từ biến môi trường (hoặc file .env).

Mọi trường đều có giá trị mặc định để app khởi động được khi chạy test.
Việc kiểm tra "thiếu cấu hình bắt buộc" nằm ở bước bootstrap, không nằm ở đây.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Đọc .env ở thư mục gốc repo (dùng chung với Docker).
    # Nếu có thêm .env trong backend/ thì file đó được ưu tiên.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # Đăng nhập Google
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = ""
    bootstrap_admin_email: str = ""

    # Google Sheets
    google_service_account_json: str = ""
    system_spreadsheet_id: str = ""

    # GitHub App (từ M2)
    github_app_id: str = ""
    github_app_private_key: str = ""

    # AI (sau này; M4 chưa dùng)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"

    # Chạy test bằng Playwright (M4)
    max_cases_per_run: int = 200
    case_timeout_seconds: int = 120
    step_timeout_ms: int = 10_000
    app_start_timeout_seconds: int = 120
    # Thư mục lưu ảnh chụp lỗi, và file cấu hình app của từng dự án (chỉ có trên máy worker)
    artifacts_dir: Path = Path("artifacts")
    worker_config_path: Path = Path("worker-projects.json")

    # Hạ tầng
    redis_url: str = "redis://localhost:6379/0"
    app_base_url: str = "http://localhost:3000"

    # Thời gian sống
    session_ttl_seconds: int = 7 * 24 * 60 * 60  # 7 ngày
    user_cache_ttl_seconds: int = 5 * 60  # 5 phút
    # Cache danh sách case/việc/màn hình của dự án. Ngắn, vì ghi xong là xoá cache ngay.
    # Chỉ bị "cũ" khi có người sửa thẳng trên Google Sheet (không qua app).
    sheet_cache_ttl_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()

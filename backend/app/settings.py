"""Đọc cấu hình từ biến môi trường (hoặc file .env).

Mọi trường đều có giá trị mặc định để app khởi động được khi chạy test.
Việc kiểm tra "thiếu cấu hình bắt buộc" nằm ở bước bootstrap, không nằm ở đây.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Đọc .env ở thư mục gốc repo (dùng chung với Docker).
    # Nếu có thêm .env trong backend/ thì file đó được ưu tiên.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # Đăng nhập Google
    session_secret: str = ""
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""

    # Google Sheets
    google_service_account_json: str = ""
    system_spreadsheet_id: str = ""

    # GitHub App (từ M2)
    github_app_id: str = ""
    github_app_private_key: str = ""

    # Agent bên ngoài chỉ được phép ghi kết quả; để trống thì tắt API.
    agent_api_token: str = ""

    # Cloudinary: nơi lưu ảnh/video. Secret chỉ ở backend, không bao giờ trả ra ngoài.
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # AI (từ M4)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"
    case_timeout_seconds: int = 300
    max_cases_per_run: int = 200

    # Hạ tầng
    redis_url: str = "redis://localhost:6379/0"
    app_base_url: str = "http://localhost:3000"

    # Thời gian sống
    session_ttl_seconds: int = 7 * 24 * 60 * 60  # 7 ngày
    # Sai mật khẩu bao nhiêu lần thì khoá 15 phút. Đặt 0 để tắt khoá (chỉ khi đang test).
    login_max_failures: int = 5
    user_cache_ttl_seconds: int = 5 * 60  # 5 phút
    # Cache danh sách case/việc/màn hình của dự án. Ngắn, vì ghi xong là xoá cache ngay.
    # Chỉ bị "cũ" khi có người sửa thẳng trên Google Sheet (không qua app).
    sheet_cache_ttl_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()

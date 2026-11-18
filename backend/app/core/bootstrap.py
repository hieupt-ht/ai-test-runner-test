"""Chuẩn bị file Sheet hệ thống khi app khởi động.

- Tab nào còn thiếu thì tạo, kèm hàng tiêu đề.
- Tab đã có thì tự thêm các cột còn thiếu vào cuối tiêu đề.
- Tab Users còn trống thì thêm Admin đầu tiên (từ BOOTSTRAP_ADMIN_EMAIL + BOOTSTRAP_ADMIN_PASSWORD).
Chạy nhiều lần vẫn cho cùng kết quả.
"""

import logging

from app.core.models.user import Role, User, normalize_email
from app.core.passwords import hash_password
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import PROJECT_TABS, SYSTEM_TABS
from app.core.sheets.table import SheetTable
from app.core.time import utc_now

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Thiếu cấu hình bắt buộc khi chạy thật."""


def _ensure_tabs(
    gateway: SheetsGateway, spreadsheet_id: str, tabs: dict[str, list[str]]
) -> list[str]:
    """Tạo các tab còn thiếu (kèm tiêu đề); tab đã có thì thêm cột còn thiếu vào cuối."""
    existing_tabs = set(gateway.list_tabs(spreadsheet_id))
    created_tabs: list[str] = []
    for tab, columns in tabs.items():
        if tab in existing_tabs:
            SheetTable(gateway, spreadsheet_id, tab, columns).ensure_columns()
        else:
            gateway.add_tab(spreadsheet_id, tab, columns)
            created_tabs.append(tab)
    return created_tabs


def bootstrap_system_spreadsheet(
    gateway: SheetsGateway,
    spreadsheet_id: str,
    users: UserRepository,
    bootstrap_admin_email: str,
    bootstrap_admin_password: str = "",
) -> list[str]:
    created_tabs = _ensure_tabs(gateway, spreadsheet_id, SYSTEM_TABS)

    admin_email = normalize_email(bootstrap_admin_email)
    if admin_email and users.is_empty():
        if not bootstrap_admin_password:
            raise ConfigError("Thiếu BOOTSTRAP_ADMIN_PASSWORD trong .env")
        users.create(
            User(
                email=admin_email,
                name="Admin",
                role=Role.ADMIN,
                active=True,
                created_at=utc_now(),
            ),
            password_hash=hash_password(bootstrap_admin_password),
        )
    elif (
        admin_email
        and bootstrap_admin_password
        and users.get(admin_email) is not None
        and not users.get_password_hash(admin_email)
    ):
        # Admin đã có từ bản cũ (chưa có mật khẩu): đặt mật khẩu từ .env, chỉ khi hash đang trống.
        users.set_password_hash(admin_email, hash_password(bootstrap_admin_password))

    return created_tabs


def bootstrap_project_spreadsheet(gateway: SheetsGateway, spreadsheet_id: str) -> list[str]:
    """Chuẩn bị Sheet riêng của một dự án. Đây cũng là bước kiểm tra app có quyền ghi.

    App chưa được share quyền thì gateway báo SheetAccessDeniedError.
    """
    return _ensure_tabs(gateway, spreadsheet_id, PROJECT_TABS)


def upgrade_project_spreadsheets(projects: ProjectRepository, gateway: SheetsGateway) -> None:
    """Nâng cấp Sheet của mọi dự án chưa lưu trữ (thêm cột mới ở cuối nếu thiếu).

    Một dự án lỗi (mất quyền, Sheet bị xoá...) chỉ ghi log, không chặn các dự án còn lại.
    """
    for project in projects.list_all():
        if project.archived:
            continue
        try:
            bootstrap_project_spreadsheet(gateway, project.spreadsheet_id)
        except Exception:
            logger.warning("Không nâng cấp được Sheet của dự án %s", project.id, exc_info=True)

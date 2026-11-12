"""Chuẩn bị file Sheet hệ thống khi app khởi động.

- Tab nào còn thiếu thì tạo, kèm hàng tiêu đề.
- Tab đã có thì kiểm tra đủ cột.
- Tab Users còn trống thì thêm Admin đầu tiên (từ BOOTSTRAP_ADMIN_EMAIL).
Chạy nhiều lần vẫn cho cùng kết quả.
"""

from app.core.models.user import Role, User, normalize_email
from app.core.repositories.users import UserRepository
from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import SYSTEM_TABS
from app.core.sheets.table import SheetTable
from app.core.time import utc_now


class ConfigError(Exception):
    """Thiếu cấu hình bắt buộc khi chạy thật."""


def bootstrap_system_spreadsheet(
    gateway: SheetsGateway, spreadsheet_id: str, users: UserRepository, bootstrap_admin_email: str
) -> list[str]:
    existing_tabs = set(gateway.list_tabs(spreadsheet_id))
    created_tabs: list[str] = []

    for tab, columns in SYSTEM_TABS.items():
        if tab in existing_tabs:
            SheetTable(gateway, spreadsheet_id, tab, columns).check_columns()
        else:
            gateway.add_tab(spreadsheet_id, tab, columns)
            created_tabs.append(tab)

    admin_email = normalize_email(bootstrap_admin_email)
    if admin_email and users.is_empty():
        users.create(
            User(
                email=admin_email,
                name="Admin",
                role=Role.ADMIN,
                active=True,
                created_at=utc_now(),
            )
        )

    return created_tabs

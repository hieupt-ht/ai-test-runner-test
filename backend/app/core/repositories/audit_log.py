import json
from typing import Any

from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import AUDIT_LOG_COLUMNS, AUDIT_LOG_TAB
from app.core.sheets.table import SheetTable
from app.core.time import to_iso, utc_now


class AuditLogRepository:
    """Ghi lại mọi thay đổi dữ liệu: ai, lúc nào, làm gì, đổi những gì."""

    def __init__(self, gateway: SheetsGateway, spreadsheet_id: str) -> None:
        self._table = SheetTable(gateway, spreadsheet_id, AUDIT_LOG_TAB, AUDIT_LOG_COLUMNS)

    def record(
        self, *, actor: str, action: str, entity: str, entity_id: str, diff: dict[str, Any]
    ) -> None:
        self._table.append(
            {
                "at": to_iso(utc_now()),
                "actor": actor,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                # ensure_ascii=False để tiếng Việt vẫn đọc được khi mở Sheet
                "diff_json": json.dumps(diff, ensure_ascii=False, default=str),
            }
        )

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.core.sheets.gateway import SheetsGateway
from app.core.sheets.schema import AUDIT_LOG_COLUMNS, AUDIT_LOG_TAB
from app.core.sheets.table import SheetTable
from app.core.time import from_iso, to_iso, utc_now


class AuditEntry(BaseModel):
    """Một dòng lịch sử: ai làm gì lúc nào và đổi những gì."""

    at: datetime
    actor: str
    action: str
    diff: dict[str, Any]


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

    def list_for(self, entity: str, entity_id: str) -> list[AuditEntry]:
        """Lịch sử của một đối tượng, mới nhất trước."""
        entries = [
            AuditEntry(
                at=from_iso(record["at"]),
                actor=record["actor"],
                action=record["action"],
                diff=json.loads(record["diff_json"] or "{}"),
            )
            for record in self._table.read_all()
            if record["entity"] == entity and record["entity_id"] == entity_id
        ]
        # sort ổn định + đảo ngược: cùng một giây thì dòng ghi sau vẫn nằm trước
        entries.reverse()
        entries.sort(key=lambda entry: entry.at, reverse=True)
        return entries

    def latest_returns(self, entity: str, entity_ids: list[str]) -> dict[str, AuditEntry]:
        """Với mỗi đối tượng, lần "trả lại" gần nhất NẾU nó vẫn là lần đổi trạng thái mới nhất.

        Đối tượng đã gửi duyệt/duyệt lại sau lần trả lại thì không có mặt trong kết quả.
        Chỉ đọc tab AuditLog một lần cho cả danh sách.
        """
        wanted = set(entity_ids)
        latest: dict[str, tuple[str, AuditEntry]] = {}  # id -> (thời điểm ISO, dòng)
        for record in self._table.read_all():
            if record["entity"] != entity or record["entity_id"] not in wanted:
                continue
            diff = json.loads(record["diff_json"] or "{}")
            if "status" not in diff:
                continue  # sửa chữ, không đổi trạng thái
            entry = AuditEntry(
                at=from_iso(record["at"]),
                actor=record["actor"],
                action=record["action"],
                diff=diff,
            )
            # `>=`: cùng một giây thì dòng ghi sau (nằm dưới) thắng
            if record["entity_id"] not in latest or record["at"] >= latest[record["entity_id"]][0]:
                latest[record["entity_id"]] = (record["at"], entry)
        return {
            entity_id: entry for entity_id, (_, entry) in latest.items() if entry.action == "RETURN"
        }

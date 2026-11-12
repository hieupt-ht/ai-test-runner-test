import json

from app.core.repositories.audit_log import AuditLogRepository
from tests.conftest import SYSTEM_SHEET_ID
from tests.fakes import FakeSheetsGateway


def test_record_appends_row_with_json_diff(
    audit_log: AuditLogRepository, gateway: FakeSheetsGateway
) -> None:
    audit_log.record(
        actor="admin@x.com",
        action="UPDATE",
        entity="user",
        entity_id="an@x.com",
        diff={"role": ["TESTER", "QA_LEAD"], "name": ["An", "An Nguyễn"]},
    )

    rows = gateway.data[SYSTEM_SHEET_ID]["AuditLog"]
    assert len(rows) == 2
    at, actor, action, entity, entity_id, diff_json = rows[1]
    assert at.endswith("Z")
    assert (actor, action, entity, entity_id) == ("admin@x.com", "UPDATE", "user", "an@x.com")
    assert json.loads(diff_json) == {"role": ["TESTER", "QA_LEAD"], "name": ["An", "An Nguyễn"]}
    assert "Nguyễn" in diff_json  # giữ nguyên tiếng Việt, không bị đổi thành \u...

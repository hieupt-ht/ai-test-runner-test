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


def test_list_for_filters_and_sorts_newest_first(audit_log: AuditLogRepository) -> None:
    def record(
        actor: str, action: str, entity: str, entity_id: str, diff: dict[str, object]
    ) -> None:
        audit_log.record(actor=actor, action=action, entity=entity, entity_id=entity_id, diff=diff)

    record("a@x.com", "CREATE", "test_case", "TC-000001", {})
    record("a@x.com", "CREATE", "test_case", "TC-000002", {})
    record("b@x.com", "UPDATE", "test_case", "TC-000001", {"title": ["Cũ", "Mới"]})
    record("a@x.com", "CREATE", "screen", "TC-000001", {})

    entries = audit_log.list_for("test_case", "TC-000001")

    assert [entry.action for entry in entries] == ["UPDATE", "CREATE"]  # mới nhất trước
    assert entries[0].actor == "b@x.com"
    assert entries[0].diff == {"title": ["Cũ", "Mới"]}


def test_latest_returns_only_when_return_is_the_latest_status_change(
    audit_log: AuditLogRepository,
) -> None:
    def record(entity_id: str, action: str, diff: dict[str, object]) -> None:
        audit_log.record(
            actor="lead@x.com", action=action, entity="test_case", entity_id=entity_id, diff=diff
        )

    # TC-1: gửi duyệt -> bị trả lại (còn hiệu lực)
    record("TC-1", "SUBMIT", {"status": ["DRAFT", "IN_REVIEW"]})
    record("TC-1", "RETURN", {"status": ["IN_REVIEW", "DRAFT"], "comment": "Thiếu bước 3"})
    # TC-2: bị trả lại nhưng sau đó đã gửi duyệt lại -> hết hiệu lực
    record("TC-2", "RETURN", {"status": ["IN_REVIEW", "DRAFT"], "comment": "Cũ"})
    record("TC-2", "SUBMIT", {"status": ["DRAFT", "IN_REVIEW"]})
    # TC-3: chưa từng bị trả lại; sửa chữ (không đổi trạng thái) không tính
    record("TC-3", "UPDATE", {"title": ["a", "b"]})

    found = audit_log.latest_returns("test_case", ["TC-1", "TC-2", "TC-3"])

    assert list(found) == ["TC-1"]
    assert found["TC-1"].diff["comment"] == "Thiếu bước 3"
    assert found["TC-1"].actor == "lead@x.com"


def test_record_many_single_append(
    audit_log: AuditLogRepository, gateway: FakeSheetsGateway
) -> None:
    before = gateway.calls.count("append:AuditLog")

    audit_log.record_many(
        [
            {
                "actor": "a@x.com",
                "action": "CREATE",
                "entity": "test_case",
                "entity_id": "TC-000001",
                "diff": {"title": "Một"},
            },
            {
                "actor": "a@x.com",
                "action": "CREATE",
                "entity": "test_case",
                "entity_id": "TC-000002",
                "diff": {},
            },
        ]
    )

    assert gateway.calls.count("append:AuditLog") == before + 1
    assert audit_log.list_for("test_case", "TC-000001")[0].diff == {"title": "Một"}
    assert len(audit_log.list_for("test_case", "TC-000002")) == 1

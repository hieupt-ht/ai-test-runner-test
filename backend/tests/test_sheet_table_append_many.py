from app.core.sheets.table import SheetTable
from tests.fakes import FakeSheetsGateway

COLUMNS = ["email", "name", "role", "active", "created_at"]
CREATED = "2026-11-12T00:00:00Z"


def make_table() -> tuple[SheetTable, FakeSheetsGateway]:
    gateway = FakeSheetsGateway({"sys": {"Users": [list(COLUMNS)]}})
    return SheetTable(gateway, "sys", "Users", COLUMNS), gateway


def make_record(email: str, name: str) -> dict[str, str]:
    return {
        "email": email,
        "name": name,
        "role": "TESTER",
        "active": "TRUE",
        "created_at": CREATED,
    }


def test_append_many_writes_all_rows_in_one_call() -> None:
    table, gateway = make_table()

    table.append_many([make_record("a@x.com", "An"), make_record("b@x.com", "Bình")])

    assert gateway.calls.count("append:Users") == 1
    assert [record["email"] for record in table.read_all()] == ["a@x.com", "b@x.com"]


def test_append_many_empty_does_nothing() -> None:
    table, gateway = make_table()

    table.append_many([])

    assert "append:Users" not in gateway.calls

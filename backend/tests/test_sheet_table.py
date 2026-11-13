import pytest

from app.core.sheets.table import MissingColumnsError, SheetTable, column_letter
from tests.fakes import FakeSheetsGateway

COLUMNS = ["email", "name", "role", "active", "created_at"]
CREATED = "2026-11-12T00:00:00Z"


def make_table(rows: list[list[str]]) -> tuple[SheetTable, FakeSheetsGateway]:
    gateway = FakeSheetsGateway({"sys": {"Users": rows}})
    return SheetTable(gateway, "sys", "Users", COLUMNS), gateway


@pytest.mark.parametrize(("index", "letter"), [(0, "A"), (25, "Z"), (26, "AA"), (27, "AB")])
def test_column_letter(index: int, letter: str) -> None:
    assert column_letter(index) == letter


def test_reads_by_column_name_when_columns_reordered() -> None:
    table, _ = make_table([
        ["role", "email", "extra", "name", "active", "created_at"],
        ["ADMIN", "a@x.com", "?", "An", "TRUE", CREATED],
    ])

    assert table.read_all() == [
        {"email": "a@x.com", "name": "An", "role": "ADMIN", "active": "TRUE", "created_at": CREATED}
    ]


def test_pads_short_rows_and_skips_blank_rows() -> None:
    table, _ = make_table([
        COLUMNS,
        ["b@x.com", "Bình"],
        [],
        ["c@x.com", "Chi", "TESTER", "TRUE", CREATED],
    ])

    records = table.read_all()

    assert [record["email"] for record in records] == ["b@x.com", "c@x.com"]
    assert records[0]["role"] == ""


def test_missing_column_raises_clear_error() -> None:
    table, _ = make_table([["email", "name", "active", "created_at"]])

    with pytest.raises(MissingColumnsError, match="role"):
        table.read_all()


def test_find_row_number_reads_only_that_column() -> None:
    table, gateway = make_table([
        ["name", "email", "role", "active", "created_at"],
        ["An", "a@x.com", "ADMIN", "TRUE", CREATED],
        ["Bình", "b@x.com", "TESTER", "TRUE", CREATED],
    ])

    assert table.find_row_number("email", "b@x.com") == 3
    assert table.find_row_number("email", "khong-co@x.com") is None
    assert "Users!B:B" in gateway.calls


def test_read_row_returns_record() -> None:
    table, _ = make_table([COLUMNS, ["a@x.com", "An"]])

    assert table.read_row(2)["name"] == "An"


def test_append_writes_in_sheet_column_order() -> None:
    table, gateway = make_table([["role", "email", "extra", "name", "active", "created_at"]])

    table.append({"email": "a@x.com", "name": "An", "role": "ADMIN", "active": "TRUE",
                  "created_at": CREATED})

    assert gateway.data["sys"]["Users"][1] == ["ADMIN", "a@x.com", "", "An", "TRUE", CREATED]


def test_update_writes_values_in_sheet_column_order_and_keeps_unknown_columns() -> None:
    table, gateway = make_table([
        ["role", "email", "extra", "name", "active", "created_at"],
        ["ADMIN", "a@x.com", "giữ nguyên", "An", "TRUE", CREATED],
    ])

    table.update(2, {"email": "a@x.com", "name": "An Nguyễn", "role": "QA_LEAD",
                     "active": "FALSE", "created_at": CREATED})

    assert gateway.data["sys"]["Users"][1] == [
        "QA_LEAD", "a@x.com", "giữ nguyên", "An Nguyễn", "FALSE", CREATED
    ]


def test_row_longer_than_header_does_not_crash() -> None:
    # Ai đó gõ nhầm một ô ở bên phải cột cuối cùng
    table, _ = make_table([COLUMNS, ["a@x.com", "An", "ADMIN", "TRUE", CREATED, "ô lạc"]])

    assert table.read_all()[0]["email"] == "a@x.com"
    assert table.read_row(2)["name"] == "An"
    table.update(2, {"name": "An mới"})


def test_header_is_reread_when_columns_change_while_running() -> None:
    table, gateway = make_table([COLUMNS, ["a@x.com", "An", "ADMIN", "TRUE", CREATED]])
    table.read_all()

    # Có người đổi chỗ hai cột email và name trên Sheet trong lúc app đang chạy
    gateway.data["sys"]["Users"] = [
        ["name", "email", "role", "active", "created_at"],
        ["An", "a@x.com", "ADMIN", "TRUE", CREATED],
    ]

    assert table.read_all()[0]["email"] == "a@x.com"


def test_read_all_takes_header_from_the_same_read_as_the_data() -> None:
    table, gateway = make_table([COLUMNS, ["a@x.com", "An", "ADMIN", "TRUE", CREATED]])

    table.read_all()
    table.read_rows_numbered()

    # Hàng tiêu đề đã nằm sẵn trong lần đọc cả tab, khỏi đọc "Users!1:1" riêng.
    assert gateway.calls == ["Users", "Users"]


def test_find_record_returns_row_number_and_record_with_fewer_reads() -> None:
    table, gateway = make_table([
        COLUMNS,
        ["a@x.com", "An", "ADMIN", "TRUE", CREATED],
        ["b@x.com", "Bình", "TESTER", "TRUE", CREATED],
    ])

    found = table.find_record("email", "b@x.com")

    assert found is not None
    row_number, record = found
    assert row_number == 3
    assert record["name"] == "Bình"
    # tiêu đề (1 lần) + cột email + đúng dòng cần = 3 lượt đọc
    assert len(gateway.calls) == 3


def test_find_record_returns_none_when_missing() -> None:
    table, _ = make_table([COLUMNS, ["a@x.com", "An", "ADMIN", "TRUE", CREATED]])

    assert table.find_record("email", "zzz@x.com") is None

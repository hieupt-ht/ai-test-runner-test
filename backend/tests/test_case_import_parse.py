"""Test bộ đọc file Excel test case (hàm thuần, không đụng Google Sheets)."""

from datetime import UTC, date, datetime
from io import BytesIO
from typing import Any

from openpyxl import Workbook

from app.core.models.screen import Screen
from app.core.models.test_case import ExecutionMode, Platform, Priority, Severity, TestType
from app.core.services.case_import import (
    COLUMNS,
    MAX_CASES,
    MAX_DATA_ROWS,
    MAX_FILE_BYTES,
    ImportIssue,
    parse_workbook,
)
from tests.xlsx_helpers import HEADERS, make_xlsx


def _screen(screen_id: str, name: str) -> Screen:
    return Screen(
        id=screen_id,
        name=name,
        description="",
        route="/",
        code_paths=[],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


SCREENS = [_screen("SC-0001", "Đăng nhập"), _screen("SC-0002", "Giỏ hàng")]

# Một dòng hợp lệ (16 ô) theo thứ tự cột
_BASE: dict[str, Any] = {
    "Mã nhóm": "A1",
    "Màn hình": "Đăng nhập",
    "Mã yêu cầu": "",
    "Tiêu đề": "Đăng nhập đúng",
    "Điều kiện trước": "",
    "Dữ liệu test": "",
    "Điểm bắt đầu": "",
    "Bước làm": "Mở trang",
    "Mong đợi của bước": "",
    "Kết quả mong đợi": "Vào được trang chủ",
    "Điều kiện sau": "",
    "Mức độ": "HIGH",
    "Ưu tiên": "P1",
    "Nền tảng": "",
    "Loại test": "",
    "Regression": "",
}


def _row() -> list[Any]:
    """Một dòng hợp lệ; muốn đổi ô nào thì dùng _with."""
    return [_BASE[h] for h in HEADERS]


def _with(row: list[Any], header: str, value: Any) -> list[Any]:
    """Trả bản sao dòng với một ô đổi giá trị."""
    copy = list(row)
    copy[HEADERS.index(header)] = value
    return copy


def test_columns_are_sixteen_in_spec_order() -> None:
    assert len(COLUMNS) == 16
    assert list(_BASE) == HEADERS


def test_groups_rows_into_cases_in_order() -> None:
    base = _row()
    rows = [
        base,
        _with(base, "Bước làm", "Nhập tên"),
        _with(base, "Bước làm", "Bấm đăng nhập"),
        _with(_with(base, "Mã nhóm", "A2"), "Tiêu đề", "Đăng nhập sai"),
    ]
    result = parse_workbook(make_xlsx(rows), SCREENS)
    assert result.errors == []
    assert [c.group for c in result.cases] == ["A1", "A2"]
    first = result.cases[0]
    assert first.step_count == 3
    assert [s.action for s in first.content.steps] == ["Mở trang", "Nhập tên", "Bấm đăng nhập"]
    assert first.row == 2
    assert result.cases[1].row == 5
    assert first.screen_id == "SC-0001"
    assert first.screen_name == "Đăng nhập"
    assert first.title == "Đăng nhập đúng"
    assert first.content.execution_mode == ExecutionMode.MANUAL


def test_wrong_header_stops() -> None:
    header = list(HEADERS)
    header[3] = "Ten"
    result = parse_workbook(make_xlsx([_row()], header=header), SCREENS)
    assert result.cases == []
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error == ImportIssue(row=1, column="Ten", message=error.message)
    assert error.message.startswith("File không đúng mẫu, hãy tải file mẫu mới")


def test_header_ignores_case_spaces_and_extra_columns() -> None:
    header: list[Any] = [*HEADERS, "Ghi chú thêm"]
    header[0] = " mã NHÓM "
    rows = [[*_row(), "bỏ qua"]]
    result = parse_workbook(make_xlsx(rows, header=header), SCREENS)
    assert result.errors == []
    assert len(result.cases) == 1


def test_group_must_be_contiguous() -> None:
    a1 = _row()
    a2 = _with(a1, "Mã nhóm", "A2")
    result = parse_workbook(make_xlsx([a1, a2, a1]), SCREENS)
    assert [e.row for e in result.errors] == [4]
    assert result.errors[0].column == "Mã nhóm"


def test_case_cell_conflict_in_later_row() -> None:
    a1 = _row()
    conflict = _with(a1, "Tiêu đề", "Tiêu đề khác")
    result = parse_workbook(make_xlsx([a1, conflict]), SCREENS)
    assert len(result.errors) == 1
    assert result.errors[0].row == 3
    assert result.errors[0].column == "Tiêu đề"

    # Ô trống hoặc giống hệt ở dòng sau thì không lỗi
    blank = _with(_with(_with(a1, "Tiêu đề", ""), "Màn hình", ""), "Kết quả mong đợi", "")
    result = parse_workbook(make_xlsx([a1, blank, a1]), SCREENS)
    assert result.errors == []
    assert result.cases[0].step_count == 3


def test_blank_row_skipped_and_missing_group_is_error() -> None:
    blank: list[Any] = [None] * 16
    no_group = _with(_row(), "Mã nhóm", "")
    result = parse_workbook(make_xlsx([_row(), blank, no_group]), SCREENS)
    assert len(result.cases) == 1
    assert result.cases[0].step_count == 1
    assert len(result.errors) == 1
    assert result.errors[0].row == 4
    assert result.errors[0].column == "Mã nhóm"


def test_screen_by_name_or_id_and_ambiguous_name() -> None:
    by_name = _with(_row(), "Màn hình", "đăng nhập ")
    by_id = _with(_with(_row(), "Mã nhóm", "B"), "Màn hình", "SC-0002")
    result = parse_workbook(make_xlsx([by_name, by_id]), SCREENS)
    assert result.errors == []
    assert [c.screen_id for c in result.cases] == ["SC-0001", "SC-0002"]
    assert result.cases[1].screen_name == "Giỏ hàng"

    # Hai màn hình trùng tên: ghi tên thì lỗi, ghi mã thì được
    screens = [*SCREENS, _screen("SC-0003", "Đăng nhập")]
    result = parse_workbook(make_xlsx([by_name]), screens)
    assert [(e.row, e.column, e.message) for e in result.errors] == [
        (2, "Màn hình", "Có nhiều màn hình tên này, hãy ghi mã màn hình")
    ]
    result = parse_workbook(make_xlsx([_with(_row(), "Màn hình", "SC-0003")]), screens)
    assert result.errors == []

    result = parse_workbook(make_xlsx([_with(_row(), "Màn hình", "Không có")]), SCREENS)
    assert [(e.row, e.column) for e in result.errors] == [(2, "Màn hình")]


def test_choice_values() -> None:
    row = _with(_row(), "Mức độ", "high")
    content = parse_workbook(make_xlsx([row]), SCREENS).cases[0].content
    assert content.severity == Severity.HIGH
    assert content.priority == Priority.P1
    assert content.platform == Platform.WEB
    assert content.test_type == TestType.FUNCTIONAL
    assert content.regression is False

    bad = _with(_row(), "Ưu tiên", "P4")
    result = parse_workbook(make_xlsx([bad]), SCREENS)
    assert [(e.row, e.column) for e in result.errors] == [(2, "Ưu tiên")]

    for value in ["x", "Yes", True, "Có"]:
        result = parse_workbook(make_xlsx([_with(_row(), "Regression", value)]), SCREENS)
        assert result.errors == []
        assert result.cases[0].content.regression is True, value
    result = parse_workbook(make_xlsx([_with(_row(), "Regression", "Không")]), SCREENS)
    assert result.cases[0].content.regression is False
    result = parse_workbook(make_xlsx([_with(_row(), "Regression", "abc")]), SCREENS)
    assert [e.column for e in result.errors] == ["Regression"]

    row = _with(_with(_row(), "Nền tảng", "ios"), "Loại test", "ui")
    content = parse_workbook(make_xlsx([row]), SCREENS).cases[0].content
    assert content.platform == Platform.IOS
    assert content.test_type == TestType.UI


def test_numbers_read_as_text() -> None:
    one = _with(_with(_row(), "Mã nhóm", 1), "Dữ liệu test", date(2026, 11, 19))
    two = _with(_row(), "Mã nhóm", 2.0)
    result = parse_workbook(make_xlsx([one, two]), SCREENS)
    assert result.errors == []
    assert [c.group for c in result.cases] == ["1", "2"]
    assert result.cases[0].content.test_data.startswith("2026-11-19")


def test_more_than_50_steps_is_error_in_vietnamese() -> None:
    rows = [_with(_row(), "Bước làm", f"Bước {i}") for i in range(51)]
    result = parse_workbook(make_xlsx(rows), SCREENS)
    assert len(result.errors) == 1
    assert result.errors[0].row == 2
    assert "List should have" not in result.errors[0].message
    assert "50" in result.errors[0].message


def test_required_fields() -> None:
    row = _with(_row(), "Kết quả mong đợi", "")
    result = parse_workbook(make_xlsx([row]), SCREENS)
    assert [(e.row, e.column, e.message) for e in result.errors] == [
        (2, "Kết quả mong đợi", "Không được để trống")
    ]
    result = parse_workbook(make_xlsx([_with(_row(), "Bước làm", "")]), SCREENS)
    assert [(e.row, e.column, e.message) for e in result.errors] == [
        (2, "Bước làm", "Không được để trống")
    ]


def test_limits() -> None:
    same = [_row() for _ in range(MAX_DATA_ROWS + 1)]
    result = parse_workbook(make_xlsx(same), SCREENS)
    assert len(result.errors) == 1
    assert result.errors[0].row is None
    assert result.cases == []

    many = [_with(_row(), "Mã nhóm", f"G{i}") for i in range(MAX_CASES + 1)]
    result = parse_workbook(make_xlsx(many), SCREENS)
    assert len(result.errors) == 1
    assert result.errors[0].row is None

    result = parse_workbook(b"x" * (MAX_FILE_BYTES + 1), SCREENS)
    assert len(result.errors) == 1
    assert result.errors[0].row is None


def test_reads_first_sheet_when_name_differs() -> None:
    result = parse_workbook(make_xlsx([_row()], sheet="Sheet1"), SCREENS)
    assert result.errors == []
    assert len(result.cases) == 1


def test_ignores_guide_sheet() -> None:
    result = parse_workbook(make_xlsx([_row()], guide_sheet=True), SCREENS)
    assert result.errors == []
    assert len(result.cases) == 1


def test_not_an_xlsx() -> None:
    result = parse_workbook(b"a,b,c", SCREENS)
    assert result.errors == [ImportIssue(row=None, message="Không đọc được file .xlsx")]


def test_formula_cells_use_cached_value() -> None:
    # openpyxl khi lưu không tính công thức nên không có giá trị cache.
    # Kỳ vọng: ô công thức không có cache được coi là trống (ở đây Tiêu đề trống -> lỗi).
    row = _with(_row(), "Tiêu đề", '="Đăng " & "nhập"')
    result = parse_workbook(make_xlsx([row]), SCREENS)
    assert [(e.row, e.column) for e in result.errors] == [(2, "Tiêu đề")]


def test_errors_sorted_by_row() -> None:
    rows = [_with(_row(), "Ưu tiên", "P9"), _with(_with(_row(), "Mã nhóm", "B"), "Mức độ", "x")]
    result = parse_workbook(make_xlsx(rows), SCREENS)
    assert [e.row for e in result.errors] == [2, 3]


def test_sparse_sheet_with_huge_blank_range_is_stopped_early() -> None:
    # Sheet "phình" bằng hàng triệu dòng trống: phải dừng sớm và báo lỗi chung, không đọc hết
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Test case"
    ws.append(HEADERS)
    ws.cell(row=200_000, column=1, value="A1")
    buffer = BytesIO()
    wb.save(buffer)
    result = parse_workbook(buffer.getvalue(), SCREENS)
    assert len(result.errors) == 1
    assert result.errors[0].row is None
    assert result.cases == []

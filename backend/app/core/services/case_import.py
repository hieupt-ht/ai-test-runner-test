"""Đọc file Excel (.xlsx) theo mẫu thành danh sách test case.

Đây là hàm thuần: nhận bytes của file và danh sách màn hình, trả kết quả đọc. Không đụng
Google Sheets, không xét quyền, không xét trùng tiêu đề (bước sau làm).
"""

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any, Literal

from openpyxl import load_workbook
from pydantic import BaseModel, ValidationError

from app.core.models.screen import Screen
from app.core.models.test_case import (
    Platform,
    Priority,
    Severity,
    TestCaseContent,
    TestType,
)

SHEET_NAME = "Test case"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_DATA_ROWS = 2000
MAX_CASES = 300

_WRONG_TEMPLATE = "File không đúng mẫu, hãy tải file mẫu mới"
_REQUIRED = "Không được để trống"

# Giá trị ô Regression: chữ (đã hạ chữ thường) nào là Có, chữ nào là Không
_YES = {"có", "co", "x", "yes", "true"}
_NO = {"", "không", "khong", "no", "false"}


@dataclass(frozen=True)
class ImportColumn:
    header: str  # chữ đúng ở dòng 1, ví dụ "Mã nhóm"
    field: str | None  # tên trường TestCaseContent; None cho "Mã nhóm"/"Màn hình"/bước
    level: Literal["group", "case", "step"]
    required: bool
    choices: tuple[str, ...] = ()  # cho data validation của file mẫu


# Danh sách cột khai báo MỘT chỗ: file mẫu, bộ đọc và test đều dùng chung
COLUMNS: tuple[ImportColumn, ...] = (
    ImportColumn("Mã nhóm", None, "group", True),
    ImportColumn("Màn hình", None, "case", True),
    ImportColumn("Mã yêu cầu", "requirement_ref", "case", False),
    ImportColumn("Tiêu đề", "title", "case", True),
    ImportColumn("Điều kiện trước", "precondition", "case", False),
    ImportColumn("Dữ liệu test", "test_data", "case", False),
    ImportColumn("Điểm bắt đầu", "start_point", "case", False),
    ImportColumn("Bước làm", None, "step", True),
    ImportColumn("Mong đợi của bước", None, "step", False),
    ImportColumn("Kết quả mong đợi", "expected_result", "case", True),
    ImportColumn("Điều kiện sau", "postcondition", "case", False),
    ImportColumn("Mức độ", "severity", "case", True, tuple(s.value for s in Severity)),
    ImportColumn("Ưu tiên", "priority", "case", True, tuple(p.value for p in Priority)),
    ImportColumn("Nền tảng", "platform", "case", False, tuple(p.value for p in Platform)),
    ImportColumn("Loại test", "test_type", "case", False, tuple(t.value for t in TestType)),
    ImportColumn("Regression", "regression", "case", False, ("Có", "Không")),
)

_HEADER_OF_FIELD = {c.field: c.header for c in COLUMNS if c.field}
_COL = {c.header: i for i, c in enumerate(COLUMNS)}


class ImportIssue(BaseModel):
    row: int | None
    column: str | None = None
    message: str


class ParsedCase(BaseModel):
    group: str
    row: int  # dòng đầu của nhóm
    screen_id: str
    screen_name: str
    title: str
    step_count: int
    content: TestCaseContent  # execution_mode luôn MANUAL, không media


class ParseResult(BaseModel):
    cases: list[ParsedCase] = []
    errors: list[ImportIssue] = []
    warnings: list[ImportIssue] = []


def _file_error(message: str) -> ParseResult:
    return ParseResult(errors=[ImportIssue(row=None, message=message)])


def _cell_text(value: Any) -> str:
    """Đổi một ô về chuỗi đã cắt khoảng trắng."""
    if value is None:
        return ""
    if isinstance(value, bool):  # phải xét trước int vì bool cũng là int
        return "Có" if value else "Không"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value).strip()


class _TooManyRows(Exception):
    """Sheet có quá nhiều dòng: dừng đọc sớm để không tốn bộ nhớ."""


# Tổng số dòng được quét tối đa (kể cả dòng trống), chặn sheet phình bằng hàng triệu dòng trống
_MAX_SCANNED_ROWS = MAX_DATA_ROWS * 5 + 1


def _read_rows(data: bytes) -> list[list[str]] | None:
    """Đọc sheet dữ liệu thành các dòng 16 ô (dòng 1 là tiêu đề). None nếu không mở được.

    Dòng trống hoàn toàn không được giữ lại nhưng vẫn được đếm vào số dòng quét.
    Raise _TooManyRows nếu vượt giới hạn dòng.
    """
    try:
        wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
        ws = wb[SHEET_NAME] if SHEET_NAME in wb.sheetnames else wb.worksheets[0]
        ws.reset_dimensions()  # file xuất từ công cụ khác đôi khi khai báo kích thước sai
        rows: list[list[str]] = []
        for scanned, raw in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = [_cell_text(v) for v in raw[: len(COLUMNS)]]
            cells += [""] * (len(COLUMNS) - len(cells))
            # Giữ dòng 1 (tiêu đề), còn lại chỉ giữ dòng có dữ liệu, kèm số dòng thật
            if scanned == 1 or any(cells):
                rows.append([str(scanned), *cells])
            if scanned > _MAX_SCANNED_ROWS or len(rows) > MAX_DATA_ROWS + 1:
                raise _TooManyRows
        wb.close()
        return rows
    except _TooManyRows:
        raise
    except Exception:
        return None


def _check_header(header: list[str]) -> ImportIssue | None:
    """Dòng 1 phải đúng 16 cột theo thứ tự (không phân biệt hoa thường, bỏ khoảng trắng)."""
    for cell, column in zip(header, COLUMNS, strict=True):
        if cell.casefold() != column.header.casefold():
            return ImportIssue(
                row=1,
                column=cell or "(trống)",
                message=f'{_WRONG_TEMPLATE}. Cột này phải là "{column.header}"',
            )
    return None


def _find_screen(text: str, screens: list[Screen]) -> tuple[Screen | None, str]:
    """Tìm màn hình theo mã hoặc tên. Trả (màn hình, lỗi); lỗi rỗng nếu ổn."""
    key = text.casefold()
    for screen in screens:
        if screen.id.casefold() == key:
            return screen, ""
    named = [s for s in screens if s.name.strip().casefold() == key]
    if len(named) > 1:
        return None, "Có nhiều màn hình tên này, hãy ghi mã màn hình"
    if not named:
        return None, "Không tìm thấy màn hình này trong dự án"
    return named[0], ""


def _choice(column: ImportColumn, text: str) -> tuple[str | None, str]:
    """Chuẩn hoá giá trị chọn. Trả (giá trị, lỗi); giá trị None nghĩa là dùng mặc định/đang lỗi."""
    if column.header == "Regression":
        lowered = text.casefold()
        if lowered in _YES:
            return "true", ""
        if lowered in _NO:
            return "false", ""
        return None, "Giá trị không hợp lệ, hãy ghi Có hoặc Không"
    if not text:
        return None, _REQUIRED if column.required else ""
    for choice in column.choices:
        if choice.casefold() == text.casefold():
            return choice, ""
    return None, "Giá trị không hợp lệ, hãy chọn một trong: " + ", ".join(column.choices)


def _translate(error: Any) -> str:
    """Dịch lỗi Pydantic sang tiếng Việt."""
    kind = error["type"]
    if kind in ("missing", "string_too_short"):
        return _REQUIRED
    if kind == "string_too_long":
        return f"Quá {error['ctx']['max_length']} ký tự"
    if kind == "too_long":
        return f"Quá {error['ctx']['max_length']} bước"
    return "Giá trị không hợp lệ"


def _group_rows(
    rows: list[tuple[int, list[str]]], errors: list[ImportIssue]
) -> dict[str, list[tuple[int, list[str]]]]:
    """Gom các dòng theo Mã nhóm (nhóm phải liền nhau), ghi lỗi gom dòng vào `errors`."""
    groups: dict[str, list[tuple[int, list[str]]]] = {}
    current = ""
    for number, cells in rows:
        group = cells[_COL["Mã nhóm"]]
        if not group:
            errors.append(ImportIssue(row=number, column="Mã nhóm", message=_REQUIRED))
            continue
        if group != current and group in groups:
            errors.append(
                ImportIssue(
                    row=number,
                    column="Mã nhóm",
                    message="Các dòng của một nhóm phải nằm liền nhau",
                )
            )
            continue
        current = group
        groups.setdefault(group, []).append((number, cells))
    return groups


def _build_case(
    group: str,
    lines: list[tuple[int, list[str]]],
    screens: list[Screen],
    errors: list[ImportIssue],
) -> ParsedCase | None:
    """Dựng một case từ các dòng của nhóm; lỗi ghi vào `errors`, có lỗi thì trả None."""
    first_row, first = lines[0]
    before = len(errors)
    bad_columns: set[str] = set()  # cột đã báo lỗi, tránh báo trùng với lỗi Pydantic

    def fail(row: int, column: str, message: str) -> None:
        errors.append(ImportIssue(row=row, column=column, message=message))
        bad_columns.add(column)

    # Ô mức case ở các dòng sau phải trống hoặc giống hệt dòng đầu
    for number, cells in lines[1:]:
        for column in COLUMNS:
            if column.level != "case":
                continue
            value = cells[_COL[column.header]]
            if value and value != first[_COL[column.header]]:
                fail(number, column.header, "Khác với dòng đầu của nhóm")

    screen, screen_error = _find_screen(first[_COL["Màn hình"]], screens)
    if first[_COL["Màn hình"]] == "":
        fail(first_row, "Màn hình", _REQUIRED)
    elif screen is None:
        fail(first_row, "Màn hình", screen_error)

    data: dict[str, Any] = {}
    for col in COLUMNS:
        if col.field is None or col.level != "case":
            continue
        text = first[_COL[col.header]]
        if col.choices:
            chosen, choice_error = _choice(col, text)
            if choice_error:
                fail(first_row, col.header, choice_error)
            elif chosen is not None:
                data[col.field] = chosen == "true" if col.header == "Regression" else chosen
        else:
            data[col.field] = text
    data["steps"] = [
        {"action": cells[_COL["Bước làm"]], "expected": cells[_COL["Mong đợi của bước"]]}
        for _, cells in lines
    ]

    content: TestCaseContent | None = None
    try:
        content = TestCaseContent.model_validate(data)
    except ValidationError as exc:
        for error in exc.errors():
            loc = error["loc"]
            if loc[0] == "steps":
                # Lỗi của cả danh sách báo ở dòng đầu, lỗi của một bước báo đúng dòng đó
                row = lines[loc[1]][0] if len(loc) > 1 and isinstance(loc[1], int) else first_row
                header_name = "Mong đợi của bước" if loc[-1] == "expected" else "Bước làm"
            else:
                row, header_name = first_row, _HEADER_OF_FIELD[str(loc[0])]
            if header_name not in bad_columns:
                errors.append(ImportIssue(row=row, column=header_name, message=_translate(error)))

    if len(errors) > before or screen is None or content is None:
        return None
    return ParsedCase(
        group=group,
        row=first_row,
        screen_id=screen.id,
        screen_name=screen.name,
        title=content.title,
        step_count=len(content.steps),
        content=content,
    )


def parse_workbook(data: bytes, screens: list[Screen]) -> ParseResult:
    """Đọc file .xlsx theo mẫu. Lỗi xếp theo số dòng (lỗi chung của file đứng đầu)."""
    if len(data) > MAX_FILE_BYTES:
        return _file_error("File quá lớn, tối đa 2 MB")
    try:
        all_rows = _read_rows(data)
    except _TooManyRows:
        return _file_error(f"File có quá {MAX_DATA_ROWS} dòng dữ liệu")
    if all_rows is None:
        return _file_error("Không đọc được file .xlsx")

    header = all_rows[0][1:] if all_rows else [""] * len(COLUMNS)
    header_error = _check_header(header)
    if header_error:
        return ParseResult(errors=[header_error])

    # Mỗi dòng đã kèm số dòng thật trong file ở ô đầu; dòng trống đã được bỏ
    rows = [(int(line[0]), line[1:]) for line in all_rows[1:]]

    errors: list[ImportIssue] = []
    groups = _group_rows(rows, errors)
    if len(groups) > MAX_CASES:
        return _file_error(f"File có quá {MAX_CASES} test case, hãy chia nhỏ file")

    cases: list[ParsedCase] = []
    for group, lines in groups.items():
        case = _build_case(group, lines, screens, errors)
        if case:
            cases.append(case)
    errors.sort(key=lambda e: e.row or 0)
    return ParseResult(cases=cases, errors=errors)

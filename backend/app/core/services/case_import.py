"""Đọc file Excel (.xlsx) theo mẫu thành danh sách test case.

Đây là hàm thuần: nhận bytes của file và danh sách màn hình, trả kết quả đọc. Không đụng
Google Sheets. `parse_workbook` không xét quyền và trùng tiêu đề, việc đó do `check_import`.
"""

import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any, Literal

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import BaseModel, ValidationError

from app.core.models.module import name_key
from app.core.models.screen import Screen
from app.core.models.test_case import (
    Platform,
    Priority,
    Severity,
    TestCase,
    TestCaseContent,
    TestCaseStatus,
    TestType,
)

SHEET_NAME = "Test case"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_DATA_ROWS = 2000
MAX_CASES = 300

_WRONG_TEMPLATE = "File không đúng mẫu, hãy tải file mẫu mới"
_REQUIRED = "Không được để trống"
_NOT_ASSIGNED = "Bạn chưa được giao màn hình này"
_SCREEN_NOT_FOUND = "Không tìm thấy màn hình này trong dự án"
_SCREEN_ID = re.compile(r"^sc-\d+$", re.IGNORECASE)

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
    # Tên màn hình sẽ được tạo mới (chỉ khi nhập theo module), theo thứ tự trong file
    new_screens: list[str] = []


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
    # NFC: chữ có dấu gõ kiểu tổ hợp (NFD) vẫn so khớp được với chữ dựng sẵn
    return unicodedata.normalize("NFC", str(value)).strip()


class _TooManyRows(Exception):
    """Sheet có quá nhiều dòng: dừng đọc sớm để không tốn bộ nhớ."""


# Tổng số dòng được quét tối đa (kể cả dòng trống), chặn sheet phình bằng hàng triệu dòng trống
_MAX_SCANNED_ROWS = MAX_DATA_ROWS * 5 + 1


# Tổng dung lượng các phần trong file .xlsx sau khi giải nén (chặn file nén bom)
_MAX_UNPACKED_BYTES = 50 * 1024 * 1024
_UNREADABLE = "Không đọc được file .xlsx"


def _unpacked_size(data: bytes) -> int | None:
    """Tổng dung lượng sau giải nén theo khai báo trong file zip; None nếu không phải zip."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            return sum(item.file_size for item in archive.infolist())
    except zipfile.BadZipFile:
        return None


def _read_rows(data: bytes) -> list[list[str]] | None:
    """Đọc sheet dữ liệu thành các dòng 16 ô (dòng 1 là tiêu đề). None nếu không mở được.

    Dòng trống hoàn toàn không được giữ lại nhưng vẫn được đếm vào số dòng quét.
    Raise _TooManyRows nếu vượt giới hạn dòng.
    """
    try:
        wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
        try:
            return _scan_sheet(wb)
        finally:
            wb.close()
    except _TooManyRows:
        raise
    except Exception:
        return None


def _scan_sheet(wb: Any) -> list[list[str]]:
    """Đọc các dòng của sheet dữ liệu trong workbook đã mở."""
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
    return rows


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
    key = unicodedata.normalize("NFC", text).casefold()
    for screen in screens:
        if screen.id.casefold() == key:
            return screen, ""
    named = [s for s in screens if unicodedata.normalize("NFC", s.name).strip().casefold() == key]
    if len(named) > 1:
        return None, "Có nhiều màn hình tên này, hãy ghi mã màn hình"
    if not named:
        return None, _SCREEN_NOT_FOUND
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
    create_missing: bool,
) -> ParsedCase | None:
    """Dựng một case từ các dòng của nhóm; lỗi ghi vào `errors`, có lỗi thì trả None.

    `create_missing`: tên màn hình chưa có thì không lỗi, case mang `screen_id` rỗng và tên
    đó (để service tạo màn hình mới); riêng mã `SC-xxxx` không có trong `screens` vẫn là lỗi.
    """
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

    screen_text = first[_COL["Màn hình"]]
    screen, screen_error = _find_screen(screen_text, screens)
    new_screen_name = ""
    if screen_text == "":
        fail(first_row, "Màn hình", _REQUIRED)
    elif screen is None:
        if create_missing and screen_error == _SCREEN_NOT_FOUND:
            if _SCREEN_ID.match(screen_text):
                fail(first_row, "Màn hình", f"Màn hình {screen_text.upper()} thuộc module khác")
            else:
                new_screen_name = screen_text
        else:
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

    if len(errors) > before or content is None or (screen is None and not new_screen_name):
        return None
    return ParsedCase(
        group=group,
        row=first_row,
        screen_id=screen.id if screen else "",
        screen_name=screen.name if screen else new_screen_name,
        title=content.title,
        step_count=len(content.steps),
        content=content,
    )


def parse_workbook(
    data: bytes, screens: list[Screen], *, create_missing: bool = False
) -> ParseResult:
    """Đọc file .xlsx theo mẫu. Lỗi xếp theo số dòng (lỗi chung của file đứng đầu).

    `create_missing=True` (nhập theo module): tên màn hình chưa có không phải lỗi mà được gom
    vào `ParseResult.new_screens` để tạo mới.
    """
    if len(data) > MAX_FILE_BYTES:
        return _file_error("File quá lớn, tối đa 2 MB")
    unpacked = _unpacked_size(data)
    if unpacked is None:
        return _file_error(_UNREADABLE)
    if unpacked > _MAX_UNPACKED_BYTES:
        return _file_error("File quá lớn sau khi giải nén")
    try:
        all_rows = _read_rows(data)
    except _TooManyRows:
        return _file_error(f"File có quá {MAX_DATA_ROWS} dòng dữ liệu")
    if all_rows is None:
        return _file_error(_UNREADABLE)

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
        case = _build_case(group, lines, screens, errors, create_missing)
        if case:
            cases.append(case)
    errors.sort(key=lambda e: e.row or 0)
    new_screens = _unify_new_screens(cases)
    return ParseResult(cases=cases, errors=errors, new_screens=new_screens)


def _unify_new_screens(cases: list[ParsedCase]) -> list[str]:
    """Gom tên màn hình mới theo khoá so tên; mọi case dùng cách viết của lần xuất hiện đầu."""
    spelling: dict[str, str] = {}
    for case in cases:
        if not case.screen_id:
            spelling.setdefault(name_key(case.screen_name), case.screen_name)
    for case in cases:
        if not case.screen_id:
            case.screen_name = spelling[name_key(case.screen_name)]
    return list(spelling.values())


# Case ở hai trạng thái này coi như không còn dùng: trùng tiêu đề với chúng thì không cảnh báo
_INACTIVE = {TestCaseStatus.ARCHIVED, TestCaseStatus.DEPRECATED}


def _title_key(title: str) -> str:
    """Khoá so tiêu đề: bỏ khoảng trắng hai đầu, không phân biệt hoa thường."""
    return title.strip().casefold()


def check_import(
    result: ParseResult, *, existing: list[TestCase], allowed_screen_ids: set[str] | None
) -> ParseResult:
    """Kiểm tra thêm sau khi đọc file: quyền theo màn hình và trùng tiêu đề (hàm thuần).

    `allowed_screen_ids` là các màn hình người nhập được ghi; None nghĩa là mọi màn hình
    (QA Lead/Admin). Trùng tiêu đề chỉ là cảnh báo, không chặn việc nhập.
    """
    errors = list(result.errors)
    warnings = list(result.warnings)
    used_titles = {
        (case.screen_id, _title_key(case.title))
        for case in existing
        if case.status not in _INACTIVE
    }
    for case in result.cases:
        if allowed_screen_ids is not None and case.screen_id not in allowed_screen_ids:
            errors.append(ImportIssue(row=case.row, column="Màn hình", message=_NOT_ASSIGNED))
        elif (case.screen_id, _title_key(case.title)) in used_titles:
            warnings.append(
                ImportIssue(
                    row=case.row, message=f"Màn hình {case.screen_name} đã có case cùng tiêu đề"
                )
            )
    errors.sort(key=lambda e: e.row or 0)
    return ParseResult(
        cases=result.cases, errors=errors, warnings=warnings, new_screens=result.new_screens
    )


# Màn hình dùng trong case ví dụ của file mẫu
_EXAMPLE_SCREEN = "Đăng nhập"

# Nội dung sheet "Hướng dẫn": mỗi chuỗi là một dòng
_GUIDE_LINES = (
    "HƯỚNG DẪN NHẬP TEST CASE TỪ FILE EXCEL",
    "LƯU Ý: Xoá case ví dụ (dòng 2-4 ở sheet 'Test case') trước khi nhập, nếu không nó"
    " sẽ được nhập như case thật.",
    "",
    "Cách làm: điền sheet 'Test case', lưu file .xlsx, rồi chọn file ở nút Nhập từ Excel.",
    "Giữ nguyên dòng 1 (tiêu đề cột): không đổi chữ, không đổi thứ tự, không xoá cột.",
    "Dữ liệu bắt đầu từ dòng 2. Dòng trống hoàn toàn sẽ được bỏ qua.",
    "",
    "Gom dòng thành một case",
    "- Các dòng cùng 'Mã nhóm' là một test case; mỗi dòng là một bước theo thứ tự từ trên xuống.",
    "- Các ô của case (màn hình, tiêu đề...) ghi ở dòng đầu của nhóm. Ở dòng sau để trống,"
    " hoặc ghi giống hệt dòng đầu.",
    "- Các dòng của một nhóm phải nằm liền nhau. Mỗi dòng có dữ liệu đều phải có 'Mã nhóm'.",
    "",
    "Cột Màn hình",
    "- Ghi tên màn hình trong dự án (không phân biệt hoa thường).",
    "- Nếu hai màn hình trùng tên thì ghi mã màn hình, ví dụ SC-0001.",
    "- Tester chỉ nhập được vào màn hình mình đã được giao.",
    "",
    "Cột bắt buộc",
    "- Mã nhóm, Màn hình, Tiêu đề, Bước làm (mỗi dòng), Kết quả mong đợi, Mức độ, Ưu tiên.",
    "",
    "Cột chọn giá trị (đã có danh sách chọn sẵn)",
    "- Mức độ: LOW / MEDIUM / HIGH. Ưu tiên: P1 / P2 / P3.",
    "- Nền tảng: WEB / ANDROID / IOS (để trống là WEB).",
    "- Loại test: FUNCTIONAL / UI (để trống là FUNCTIONAL).",
    "- Regression: Có / Không (để trống là Không).",
    "",
    "Giới hạn",
    f"- File tối đa {MAX_FILE_BYTES // (1024 * 1024)} MB, {MAX_DATA_ROWS} dòng dữ liệu,"
    f" {MAX_CASES} test case mỗi lần. Chỉ nhận file .xlsx.",
    "- Tối đa 50 bước mỗi case.",
    "",
    "Khi nhập xong, case ở trạng thái Nháp và là case test tay. Ảnh/video gắn thêm trong app.",
    "Nếu file còn lỗi, app báo lỗi theo từng dòng và không nhập case nào.",
)


def build_template() -> bytes:
    """Dựng file mẫu .xlsx: tiêu đề, danh sách chọn, một case ví dụ 3 bước và sheet hướng dẫn."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = SHEET_NAME
    ws.append([c.header for c in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"

    # Danh sách chọn sẵn cho các cột có giá trị cố định, áp cho các dòng dữ liệu cho phép
    last_row = MAX_DATA_ROWS + 1
    for index, column in enumerate(COLUMNS, start=1):
        letter = get_column_letter(index)
        ws.column_dimensions[letter].width = max(14, len(column.header) + 4)
        if not column.choices:
            continue
        validation = DataValidation(
            type="list", formula1='"' + ",".join(column.choices) + '"', allow_blank=True
        )
        validation.add(f"{letter}2:{letter}{last_row}")
        ws.add_data_validation(validation)

    # Case ví dụ: 3 dòng cùng mã nhóm; ô mức case chỉ ghi ở dòng đầu
    case_cells = {
        "Mã nhóm": "A1",
        "Màn hình": _EXAMPLE_SCREEN,
        "Tiêu đề": "Đăng nhập thành công bằng email hợp lệ",
        "Điều kiện trước": "Đã có tài khoản",
        "Kết quả mong đợi": "Người dùng vào được trang chủ",
        "Mức độ": "HIGH",
        "Ưu tiên": "P1",
        "Nền tảng": "WEB",
        "Loại test": "FUNCTIONAL",
        "Regression": "Có",
    }
    steps = (
        ("Mở trang đăng nhập", "Thấy form đăng nhập"),
        ("Nhập email và mật khẩu đúng", ""),
        ("Bấm nút Đăng nhập", "Chuyển sang trang chủ"),
    )
    for number, (action, expected) in enumerate(steps):
        row = case_cells if number == 0 else {"Mã nhóm": "A1"}
        row = {**row, "Bước làm": action, "Mong đợi của bước": expected}
        ws.append([row.get(c.header, "") for c in COLUMNS])

    guide = wb.create_sheet("Hướng dẫn")
    for line in _GUIDE_LINES:
        guide.append([line])
    guide["A1"].font = Font(bold=True, size=14)
    guide.column_dimensions["A"].width = 100

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

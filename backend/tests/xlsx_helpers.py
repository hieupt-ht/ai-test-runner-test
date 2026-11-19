"""Dựng file .xlsx trong bộ nhớ cho các test nhập test case."""

from io import BytesIO
from typing import Any

from openpyxl import Workbook

from app.core.services.case_import import COLUMNS, SHEET_NAME

# Dòng tiêu đề đúng mẫu: chữ lấy từ danh sách cột dùng chung
HEADERS = [c.header for c in COLUMNS]


def make_xlsx(
    rows: list[list[Any]],
    *,
    header: list[Any] | None = None,
    sheet: str = SHEET_NAME,
    guide_sheet: bool = False,
) -> bytes:
    """Tạo file .xlsx: dòng 1 là tiêu đề, các dòng sau là `rows`.

    guide_sheet=True thêm sheet "Hướng dẫn" đứng trước sheet dữ liệu.
    """
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    if guide_sheet:
        ws.title = "Hướng dẫn"
        ws.append(["Đây là hướng dẫn, không phải dữ liệu"])
        ws = wb.create_sheet(sheet)
    else:
        ws.title = sheet
    ws.append(HEADERS if header is None else header)
    for row in rows:
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

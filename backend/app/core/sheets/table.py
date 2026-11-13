"""Đọc/ghi một tab của Google Sheet theo TÊN CỘT (hàng 1), không theo vị trí cột.

Nhờ vậy, người khác đổi thứ tự cột hay thêm cột lạ vào Sheet thì code vẫn đúng.
Hàng tiêu đề được đọc lại ở mỗi thao tác (không nhớ lâu dài), để nếu ai đó đổi cột
trong lúc app đang chạy thì code vẫn đọc/ghi đúng chỗ. Khi đã đọc cả tab thì lấy luôn hàng
đầu làm tiêu đề, khỏi tốn thêm một lượt gọi Google.
"""

from app.core.sheets.gateway import SheetsGateway

Record = dict[str, str]


class MissingColumnsError(Exception):
    """Tab trong Sheet thiếu cột mà code cần."""


def column_letter(index: int) -> str:
    """Đổi chỉ số cột (bắt đầu từ 0) sang chữ cái của Sheet: 0→A, 25→Z, 26→AA."""
    letters = ""
    number = index + 1
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _fit(row: list[str], length: int) -> list[str]:
    """Đưa dòng về đúng số cột của tiêu đề.

    - Google bỏ các ô trống ở cuối dòng, nên phải đệm thêm "".
    - Ô bị gõ lạc ra ngoài cột cuối cùng thì bỏ qua.
    """
    return (row + [""] * length)[:length]


class SheetTable:
    def __init__(
        self, gateway: SheetsGateway, spreadsheet_id: str, tab: str, columns: list[str]
    ) -> None:
        self._gateway = gateway
        self._spreadsheet_id = spreadsheet_id
        self._tab = tab
        self._columns = columns

    def _check_header(self, header: list[str]) -> list[str]:
        """Kiểm tra hàng tiêu đề có đủ các cột cần dùng."""
        missing = [column for column in self._columns if column not in header]
        if missing:
            raise MissingColumnsError(f"Tab '{self._tab}' thiếu cột: {', '.join(missing)}")
        return header

    def _read_header(self) -> list[str]:
        """Đọc riêng hàng tiêu đề (một lượt đọc nhỏ)."""
        rows = self._gateway.get_values(self._spreadsheet_id, f"{self._tab}!1:1")
        return self._check_header(rows[0] if rows else [])

    def check_columns(self) -> None:
        """Báo MissingColumnsError nếu tab thiếu cột cần dùng."""
        self._read_header()

    def _read_raw_row(self, row_number: int, header: list[str]) -> list[str]:
        rows = self._gateway.get_values(
            self._spreadsheet_id, f"{self._tab}!{row_number}:{row_number}"
        )
        return _fit(rows[0] if rows else [], len(header))

    def _to_record(self, row: list[str], header: list[str]) -> Record:
        cells = dict(zip(header, _fit(row, len(header)), strict=True))
        return {column: cells[column] for column in self._columns}

    def _read_tab(self) -> tuple[list[str], list[list[str]]]:
        """Đọc cả tab một lần: hàng đầu là tiêu đề, phần còn lại là dữ liệu."""
        rows = self._gateway.get_values(self._spreadsheet_id, self._tab)
        header = self._check_header(rows[0] if rows else [])
        return header, rows[1:]

    def read_all(self) -> list[Record]:
        header, data_rows = self._read_tab()
        return [
            self._to_record(row, header) for row in data_rows if any(cell != "" for cell in row)
        ]

    def read_rows_numbered(self) -> list[tuple[int, Record]]:
        """Như read_all, nhưng kèm số dòng thật trên Sheet (dòng 1 là tiêu đề)."""
        header, data_rows = self._read_tab()
        return [
            (row_number, self._to_record(row, header))
            for row_number, row in enumerate(data_rows, start=2)
            if any(cell != "" for cell in row)
        ]

    def find_row_number(self, column: str, value: str) -> int | None:
        """Tìm số dòng (bắt đầu từ 1, như trên Sheet) có `column` bằng `value`.

        Chỉ đọc đúng một cột để tiết kiệm lượt gọi Google.
        """
        return self._find_row_number(column, value, self._read_header())

    def _find_row_number(self, column: str, value: str, header: list[str]) -> int | None:
        letter = column_letter(header.index(column))
        cells = self._gateway.get_values(self._spreadsheet_id, f"{self._tab}!{letter}:{letter}")
        for row_number, cell in enumerate(cells, start=1):
            is_header = row_number == 1
            if not is_header and cell and cell[0] == value:
                return row_number
        return None

    def find_record(self, column: str, value: str) -> tuple[int, Record] | None:
        """Như find_row_number rồi read_row, nhưng chỉ đọc tiêu đề MỘT lần."""
        header = self._read_header()
        row_number = self._find_row_number(column, value, header)
        if row_number is None:
            return None
        return row_number, self._to_record(self._read_raw_row(row_number, header), header)

    def read_row(self, row_number: int) -> Record:
        header = self._read_header()
        return self._to_record(self._read_raw_row(row_number, header), header)

    def append(self, record: Record) -> None:
        header = self._read_header()
        row = [record.get(column, "") for column in header]
        self._gateway.append_rows(self._spreadsheet_id, self._tab, [row])

    def update(self, row_number: int, record: Record) -> None:
        """Ghi đè các cột mình quản lý; các cột lạ trong Sheet được giữ nguyên."""
        header = self._read_header()
        current = self._read_raw_row(row_number, header)
        new_row = [
            record.get(column, old_value) if column in self._columns else old_value
            for column, old_value in zip(header, current, strict=True)
        ]
        self._gateway.update_row(self._spreadsheet_id, self._tab, row_number, new_row)

    def delete_row(self, row_number: int) -> None:
        """Xoá hẳn một dòng; các dòng bên dưới dịch lên. Chỉ gọi khi đang giữ khoá của tab."""
        if row_number < 2:
            raise ValueError("Không được xoá hàng tiêu đề")
        self._gateway.delete_row(self._spreadsheet_id, self._tab, row_number)

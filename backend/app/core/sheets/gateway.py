"""Lớp mỏng bọc Google Sheets API.

Đây là file DUY NHẤT trong dự án được import `googleapiclient`.
Mọi chỗ khác chỉ biết tới `SheetsGateway` (Protocol), nên test có thể thay bằng bản giả.
"""

import random
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetAccessDeniedError(Exception):
    """Service account không có quyền với Sheet này (chưa share, hoặc sai ID)."""


class SheetsGateway(Protocol):
    def get_values(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]: ...

    def append_rows(self, spreadsheet_id: str, tab: str, rows: list[list[str]]) -> None: ...

    def update_row(
        self, spreadsheet_id: str, tab: str, row_number: int, values: list[str]
    ) -> None: ...

    def update_rows(
        self, spreadsheet_id: str, tab: str, rows: dict[int, list[str]]
    ) -> None:
        """Ghi nhiều dòng (số dòng -> giá trị cả dòng) bằng đúng một lời gọi Google."""
        ...

    def list_tabs(self, spreadsheet_id: str) -> list[str]: ...

    def add_tab(self, spreadsheet_id: str, tab: str, header: list[str]) -> None: ...

    def delete_row(self, spreadsheet_id: str, tab: str, row_number: int) -> None: ...

    def delete_rows(self, spreadsheet_id: str, tab: str, row_numbers: list[int]) -> None: ...


def _is_retryable(error: HttpError) -> bool:
    """429 = Google báo gọi quá nhiều; 5xx = lỗi tạm thời phía Google."""
    status = int(error.resp.status)
    return status == 429 or status >= 500


def with_retry[T](
    call: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Gọi `call`; nếu Google báo lỗi tạm thời thì chờ lâu dần rồi thử lại."""
    for attempt in range(max_attempts):
        try:
            return call()
        except HttpError as error:
            is_last_attempt = attempt == max_attempts - 1
            if is_last_attempt or not _is_retryable(error):
                raise
            # Chờ 0.5s, 1s, 2s, 4s... cộng thêm một chút ngẫu nhiên (jitter)
            # để nhiều request không cùng thử lại một lúc.
            delay = base_delay_seconds * 2**attempt + random.uniform(0, base_delay_seconds)
            sleep(delay)
    raise AssertionError("unreachable")


def _call[T](call: Callable[[], T]) -> T:
    """Gọi Google (có thử lại); 403/404 đổi thành SheetAccessDeniedError cho dễ hiểu."""
    try:
        return with_retry(call)
    except HttpError as error:
        if int(error.resp.status) in (403, 404):
            raise SheetAccessDeniedError(str(error)) from error
        raise


class GoogleSheetsGateway:
    """Cài đặt thật, gọi Google Sheets API bằng service account."""

    def __init__(self, service_account_info: dict[str, Any]) -> None:
        self._credentials = Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            service_account_info, scopes=SCOPES
        )
        # Client của googleapiclient không an toàn khi dùng chung giữa nhiều thread,
        # nên mỗi thread giữ một client riêng.
        self._local = threading.local()

    @property
    def service_account_email(self) -> str:
        """Email cần được share quyền Editor trên mỗi file Sheet."""
        return str(self._credentials.service_account_email)

    def _spreadsheets(self) -> Any:
        if not hasattr(self._local, "service"):
            self._local.service = build(
                "sheets", "v4", credentials=self._credentials, cache_discovery=False
            )
        return self._local.service.spreadsheets()

    def get_values(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]:
        response = _call(
            lambda: self._spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=a1_range)
            .execute()
        )
        values: list[list[str]] = response.get("values", [])
        return values

    def append_rows(self, spreadsheet_id: str, tab: str, rows: list[list[str]]) -> None:
        _call(
            lambda: self._spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=f"{tab}!A1",
                valueInputOption="RAW",
                # OVERWRITE: ghi vào ô trống ngay sau bảng, không chèn dòng mới,
                # nên các dòng có sẵn không bị đẩy xuống.
                insertDataOption="OVERWRITE",
                body={"values": rows},
            )
            .execute()
        )

    def update_row(self, spreadsheet_id: str, tab: str, row_number: int, values: list[str]) -> None:
        _call(
            lambda: self._spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=f"{tab}!A{row_number}",
                valueInputOption="RAW",
                body={"values": [values]},
            )
            .execute()
        )

    def update_rows(self, spreadsheet_id: str, tab: str, rows: dict[int, list[str]]) -> None:
        if not rows:
            return
        data = [
            {"range": f"{tab}!A{row_number}", "values": [values]}
            for row_number, values in rows.items()
        ]
        _call(
            lambda: self._spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "RAW", "data": data},
            )
            .execute()
        )

    def list_tabs(self, spreadsheet_id: str) -> list[str]:
        response = _call(
            lambda: self._spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        return [sheet["properties"]["title"] for sheet in response.get("sheets", [])]

    def add_tab(self, spreadsheet_id: str, tab: str, header: list[str]) -> None:
        _call(
            lambda: self._spreadsheets()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
            )
            .execute()
        )
        self.update_row(spreadsheet_id, tab, 1, header)

    def delete_row(self, spreadsheet_id: str, tab: str, row_number: int) -> None:
        sheet_id = self._sheet_id(spreadsheet_id, tab)
        _call(
            lambda: self._spreadsheets()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [
                        {
                            "deleteDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": row_number - 1,  # Google đếm từ 0
                                    "endIndex": row_number,
                                }
                            }
                        }
                    ]
                },
            )
            .execute()
        )

    def delete_rows(self, spreadsheet_id: str, tab: str, row_numbers: list[int]) -> None:
        """Xoá nhiều dòng bằng MỘT lượt gọi Google (xếp từ dòng dưới lên để số dòng không lệch)."""
        if not row_numbers:
            return
        sheet_id = self._sheet_id(spreadsheet_id, tab)
        requests = [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": row_number - 1,
                        "endIndex": row_number,
                    }
                }
            }
            for row_number in sorted(set(row_numbers), reverse=True)
        ]
        _call(
            lambda: self._spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
            .execute()
        )

    def _sheet_id(self, spreadsheet_id: str, tab: str) -> int:
        """Số hiệu nội bộ của tab (khác với tên tab), cần cho thao tác xoá dòng."""
        response = _call(
            lambda: self._spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
            .execute()
        )
        for sheet in response.get("sheets", []):
            if sheet["properties"]["title"] == tab:
                return int(sheet["properties"]["sheetId"])
        raise SheetAccessDeniedError(f"Không tìm thấy tab {tab}")

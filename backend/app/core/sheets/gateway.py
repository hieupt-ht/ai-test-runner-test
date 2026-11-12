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


class SheetsGateway(Protocol):
    def get_values(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]: ...

    def append_rows(self, spreadsheet_id: str, tab: str, rows: list[list[str]]) -> None: ...

    def update_row(
        self, spreadsheet_id: str, tab: str, row_number: int, values: list[str]
    ) -> None: ...

    def list_tabs(self, spreadsheet_id: str) -> list[str]: ...

    def add_tab(self, spreadsheet_id: str, tab: str, header: list[str]) -> None: ...


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


class GoogleSheetsGateway:
    """Cài đặt thật, gọi Google Sheets API bằng service account."""

    def __init__(self, service_account_info: dict[str, Any]) -> None:
        self._credentials = Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            service_account_info, scopes=SCOPES
        )
        # Client của googleapiclient không an toàn khi dùng chung giữa nhiều thread,
        # nên mỗi thread giữ một client riêng.
        self._local = threading.local()

    def _spreadsheets(self) -> Any:
        if not hasattr(self._local, "service"):
            self._local.service = build(
                "sheets", "v4", credentials=self._credentials, cache_discovery=False
            )
        return self._local.service.spreadsheets()

    def get_values(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]:
        response = with_retry(
            lambda: self._spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=a1_range)
            .execute()
        )
        values: list[list[str]] = response.get("values", [])
        return values

    def append_rows(self, spreadsheet_id: str, tab: str, rows: list[list[str]]) -> None:
        with_retry(
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
        with_retry(
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

    def list_tabs(self, spreadsheet_id: str) -> list[str]:
        response = with_retry(
            lambda: self._spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        return [sheet["properties"]["title"] for sheet in response.get("sheets", [])]

    def add_tab(self, spreadsheet_id: str, tab: str, header: list[str]) -> None:
        with_retry(
            lambda: self._spreadsheets()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
            )
            .execute()
        )
        self.update_row(spreadsheet_id, tab, 1, header)

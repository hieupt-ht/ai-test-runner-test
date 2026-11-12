"""Bản giả của Google Sheets dùng cho test.

Bắt chước hai thói quen của Google thật:
- các ô trống ở CUỐI mỗi dòng bị cắt bỏ khi trả về;
- các dòng trống ở CUỐI bảng bị cắt bỏ.
"""

import re

import httplib2
from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from googleapiclient.errors import HttpError

from app.api.oauth import GoogleIdentity

_ROW_RANGE = re.compile(r"^(?P<start>\d+):(?P<end>\d+)$")
_COLUMN_RANGE = re.compile(r"^(?P<start>[A-Z]+):(?P<end>[A-Z]+)$")


def make_http_error(status: int) -> HttpError:
    return HttpError(httplib2.Response({"status": status}), b"fake error")


def _column_index(letters: str) -> int:
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1


def _trim_row(row: list[str]) -> list[str]:
    trimmed = list(row)
    while trimmed and trimmed[-1] == "":
        trimmed.pop()
    return trimmed


def _trim_rows(rows: list[list[str]]) -> list[list[str]]:
    trimmed = [_trim_row(row) for row in rows]
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    return trimmed


class FakeSheetsGateway:
    def __init__(self, data: dict[str, dict[str, list[list[str]]]] | None = None) -> None:
        self.data = data if data is not None else {}
        self.calls: list[str] = []

    def _tab(self, spreadsheet_id: str, tab: str) -> list[list[str]]:
        return self.data.setdefault(spreadsheet_id, {}).setdefault(tab, [])

    def get_values(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]:
        self.calls.append(a1_range)
        tab, _, cells = a1_range.partition("!")
        rows = self._tab(spreadsheet_id, tab)
        if not cells:
            return _trim_rows(rows)
        if match := _ROW_RANGE.match(cells):
            start, end = int(match["start"]), int(match["end"])
            return _trim_rows(rows[start - 1 : end])
        if match := _COLUMN_RANGE.match(cells):
            column = _column_index(match["start"])
            return _trim_rows([[row[column]] if column < len(row) else [] for row in rows])
        raise ValueError(f"FakeSheetsGateway không hiểu range: {a1_range}")

    def append_rows(self, spreadsheet_id: str, tab: str, rows: list[list[str]]) -> None:
        self.calls.append(f"append:{tab}")
        self._tab(spreadsheet_id, tab).extend(list(row) for row in rows)

    def update_row(self, spreadsheet_id: str, tab: str, row_number: int, values: list[str]) -> None:
        self.calls.append(f"update:{tab}!{row_number}")
        rows = self._tab(spreadsheet_id, tab)
        while len(rows) < row_number:
            rows.append([])
        rows[row_number - 1] = list(values)

    def list_tabs(self, spreadsheet_id: str) -> list[str]:
        return list(self.data.get(spreadsheet_id, {}).keys())

    def add_tab(self, spreadsheet_id: str, tab: str, header: list[str]) -> None:
        self.calls.append(f"add_tab:{tab}")
        self.data.setdefault(spreadsheet_id, {})[tab] = [list(header)]


class FakeOAuth:
    """Google giả: không gọi mạng, trả về danh tính đặt sẵn trong `identity`."""

    def __init__(self) -> None:
        self.identity = GoogleIdentity(email="an@x.com", name="An")
        self.fail_with: Exception | None = None

    async def authorize_redirect(self, request: Request, redirect_uri: str) -> Response:
        return RedirectResponse(f"https://accounts.google.com/fake?redirect_uri={redirect_uri}")

    async def fetch_identity(self, request: Request) -> GoogleIdentity:
        if self.fail_with is not None:
            raise self.fail_with
        return self.identity

"""Bản giả của Google Sheets dùng cho test.

Bắt chước hai thói quen của Google thật:
- các ô trống ở CUỐI mỗi dòng bị cắt bỏ khi trả về;
- các dòng trống ở CUỐI bảng bị cắt bỏ.
"""

import re
from collections.abc import Callable

import httplib2
from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from googleapiclient.errors import HttpError

from app.api.oauth import GoogleIdentity
from app.core.github.client import GitHubError, RepoInfo
from app.core.sheets.gateway import SheetAccessDeniedError

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
        # Spreadsheet nào nằm trong đây thì giả như app chưa được share quyền
        self.denied: set[str] = set()
        self.service_account_email = "sa@test.iam.gserviceaccount.com"
        # Móc chạy MỘT LẦN, ngay sau khi đọc xong đúng range này (trước khi trả kết quả).
        # Dùng để giả lập "request khác chen vào giữa lúc mình vừa đọc xong và sắp ghi".
        self.after_next_read: dict[str, Callable[[], None]] = {}

    def _tab(self, spreadsheet_id: str, tab: str) -> list[list[str]]:
        if spreadsheet_id in self.denied:
            raise SheetAccessDeniedError(spreadsheet_id)
        return self.data.setdefault(spreadsheet_id, {}).setdefault(tab, [])

    def get_values(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]:
        rows = self._get_values(spreadsheet_id, a1_range)
        if hook := self.after_next_read.pop(a1_range, None):
            hook()
        return rows

    def _get_values(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]:
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
        if spreadsheet_id in self.denied:
            raise SheetAccessDeniedError(spreadsheet_id)
        return list(self.data.get(spreadsheet_id, {}).keys())

    def delete_row(self, spreadsheet_id: str, tab: str, row_number: int) -> None:
        self.calls.append(f"delete:{tab}!{row_number}")
        del self._tab(spreadsheet_id, tab)[row_number - 1]

    def add_tab(self, spreadsheet_id: str, tab: str, header: list[str]) -> None:
        if spreadsheet_id in self.denied:
            raise SheetAccessDeniedError(spreadsheet_id)
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


class FakeGitHub:
    """GitHub giả: `repos` là {"org/repo": ["main", "develop"]}."""

    def __init__(self, repos: dict[str, list[str]] | None = None) -> None:
        self.repos = repos if repos is not None else {"org/web": ["develop", "main"]}

    def list_repositories(self) -> list[RepoInfo]:
        return [
            RepoInfo(full_name=name, default_branch=branches[-1], private=True)
            for name, branches in sorted(self.repos.items())
        ]

    def list_branches(self, repo_full_name: str) -> list[str]:
        if repo_full_name not in self.repos:
            raise GitHubError(f"GitHub trả lỗi 404 khi gọi {repo_full_name}")
        return sorted(self.repos[repo_full_name])

"""Bản giả của Google Sheets dùng cho test.

Bắt chước hai thói quen của Google thật:
- các ô trống ở CUỐI mỗi dòng bị cắt bỏ khi trả về;
- các dòng trống ở CUỐI bảng bị cắt bỏ.
"""

import re
from collections.abc import Callable
from typing import Literal

import httplib2
from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from googleapiclient.errors import HttpError

from app.api.oauth import GoogleIdentity
from app.core.github.client import GitHubError, IssueComment, IssueInfo, RepoInfo
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
        # Số lần gọi ghi nhiều dòng một lượt (values.batchUpdate)
        self.batch_update_calls = 0

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

    def update_rows(self, spreadsheet_id: str, tab: str, rows: dict[int, list[str]]) -> None:
        self.calls.append(f"update_rows:{tab}")
        self.batch_update_calls += 1
        for row_number, values in rows.items():
            self.update_row(spreadsheet_id, tab, row_number, values)
            self.calls.pop()  # chỉ tính là một lời gọi

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
        self.issues: dict[str, list[tuple[IssueInfo, str]]] = {}
        self.calls: list[str] = []
        self.fail_with: Exception | None = None
        self.issue_comments: dict[str, dict[int, list[IssueComment]]] = {}
        self.labels: dict[str, dict[str, str]] = {}
        # Người được giao theo số issue (test chỉ dùng một repo)
        self.assignees: dict[int, list[str]] = {}
        self.fail_assign_with: Exception | None = None

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def list_repositories(self) -> list[RepoInfo]:
        return [
            RepoInfo(full_name=name, default_branch=branches[-1], private=True)
            for name, branches in sorted(self.repos.items())
        ]

    def list_branches(self, repo_full_name: str) -> list[str]:
        if repo_full_name not in self.repos:
            raise GitHubError(f"GitHub trả lỗi 404 khi gọi {repo_full_name}")
        return sorted(self.repos[repo_full_name])

    def find_issue_by_label(self, repo_full_name: str, label: str) -> IssueInfo | None:
        self._check()
        self.calls.append("find")
        matches = [
            issue for issue, _ in self.issues.get(repo_full_name, []) if label in issue.labels
        ]
        return min(matches, key=lambda issue: issue.number) if matches else None

    def create_issue(
        self, repo_full_name: str, *, title: str, body: str, labels: list[str]
    ) -> IssueInfo:
        self._check()
        self.calls.append("create")
        items = self.issues.setdefault(repo_full_name, [])
        number = max((issue.number for issue, _ in items), default=0) + 1
        issue = IssueInfo(
            number=number,
            url=f"https://github.com/{repo_full_name}/issues/{number}",
            state="open",
            title=title,
            labels=labels,
        )
        items.append((issue, body))
        return issue

    def update_issue(
        self,
        repo_full_name: str,
        number: int,
        *,
        title: str,
        body: str,
        labels: list[str],
        state: Literal["open", "closed"],
    ) -> IssueInfo:
        self._check()
        self.calls.append("update")
        items = self.issues[repo_full_name]
        for index, (old, _) in enumerate(items):
            if old.number == number:
                issue = old.model_copy(update={"title": title, "labels": labels, "state": state})
                items[index] = (issue, body)
                return issue
        raise GitHubError("Không tìm thấy issue")

    def ensure_label(self, repo_full_name: str, name: str, *, color: str | None = None) -> None:
        self._check()
        self.calls.append(f"label:{name}")
        self.labels.setdefault(repo_full_name, {})[name] = color or ""

    def list_issue_comments(self, repo_full_name: str, issue_number: int) -> list[IssueComment]:
        self._check()
        self.calls.append("comments:list")
        return self.issue_comments.get(repo_full_name, {}).get(issue_number, [])

    def create_issue_comment(self, repo_full_name: str, issue_number: int, body: str) -> None:
        self._check()
        self.calls.append("comments:create")
        comments = self.issue_comments.setdefault(repo_full_name, {}).setdefault(issue_number, [])
        next_id = max((comment.id for comment in comments), default=0) + 1
        comments.append(IssueComment(id=next_id, body=body))

    def update_issue_comment(self, repo_full_name: str, comment_id: int, body: str) -> None:
        self._check()
        self.calls.append("comments:update")
        for comments in self.issue_comments.get(repo_full_name, {}).values():
            for index, comment in enumerate(comments):
                if comment.id == comment_id:
                    comments[index] = IssueComment(id=comment.id, body=body)
                    return
        raise GitHubError("Không tìm thấy comment")

    def add_assignees(
        self, repo_full_name: str, issue_number: int, assignees: list[str]
    ) -> None:
        self._check()
        self.calls.append("assign")
        if self.fail_assign_with is not None:
            raise self.fail_assign_with
        current = self.assignees.setdefault(issue_number, [])
        current.extend(name for name in assignees if name not in current)

    def update_issue_state_and_labels(
        self,
        repo_full_name: str,
        issue_number: int,
        *,
        state: Literal["open", "closed"],
        labels: list[str],
    ) -> None:
        self._check()
        self.calls.append("issue:state")
        items = self.issues[repo_full_name]
        for index, (old, body) in enumerate(items):
            if old.number == issue_number:
                items[index] = (old.model_copy(update={"state": state, "labels": labels}), body)
                return
        raise GitHubError("Không tìm thấy issue")

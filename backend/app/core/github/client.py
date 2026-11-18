"""Gọi GitHub bằng GitHub App (không dùng token cá nhân).

Cách GitHub App xác thực, theo 2 bước:
1. App tự ký một JWT bằng private key (sống 10 phút) để chứng minh "tôi là App số X".
2. Dùng JWT đó xin "installation token" cho từng nơi App được cài (sống khoảng 1 giờ).
   Token này mới được dùng để đọc repo.

Đây là file DUY NHẤT trong dự án được gọi GitHub. Chỗ khác chỉ biết `GitHubClient`.
"""

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal, Protocol

import httpx
import jwt
from pydantic import BaseModel

API_URL = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
TOKEN_SAFETY_SECONDS = 60  # đổi token sớm hơn hạn 1 phút cho chắc


class RepoInfo(BaseModel):
    full_name: str
    default_branch: str
    private: bool


class IssueInfo(BaseModel):
    number: int
    url: str
    state: Literal["open", "closed"]
    title: str
    labels: list[str]


class IssueComment(BaseModel):
    id: int
    body: str


class GitHubNotConfiguredError(Exception):
    pass


class GitHubError(Exception):
    """GitHub trả lỗi (sai khoá, App chưa được cài, hết quota...)."""


class GitHubClient(Protocol):
    def list_repositories(self) -> list[RepoInfo]: ...

    def list_branches(self, repo_full_name: str) -> list[str]: ...

    def find_issue_by_label(self, repo_full_name: str, label: str) -> IssueInfo | None: ...

    def create_issue(
        self, repo_full_name: str, *, title: str, body: str, labels: list[str]
    ) -> IssueInfo: ...

    def update_issue(
        self,
        repo_full_name: str,
        number: int,
        *,
        title: str,
        body: str,
        labels: list[str],
        state: Literal["open", "closed"],
    ) -> IssueInfo: ...

    def ensure_label(
        self, repo_full_name: str, name: str, *, color: str | None = None
    ) -> None: ...

    def list_issue_comments(self, repo_full_name: str, issue_number: int) -> list[IssueComment]: ...

    def create_issue_comment(self, repo_full_name: str, issue_number: int, body: str) -> None: ...

    def update_issue_comment(self, repo_full_name: str, comment_id: int, body: str) -> None: ...

    def update_issue_state_and_labels(
        self,
        repo_full_name: str,
        issue_number: int,
        *,
        state: Literal["open", "closed"],
        labels: list[str],
    ) -> None: ...

    def add_assignees(
        self, repo_full_name: str, issue_number: int, assignees: list[str]
    ) -> None: ...


def normalize_private_key(value: str) -> str:
    """Khoá trong .env thường viết trên một dòng với "\\n"; đổi lại thành xuống dòng thật."""
    return value.strip().strip("'\"").replace("\\n", "\n").strip()


class GitHubAppClient:
    def __init__(
        self,
        app_id: str,
        private_key: str,
        *,
        http: httpx.Client | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._app_id = app_id
        self._private_key = normalize_private_key(private_key)
        self._http = http or httpx.Client(base_url=API_URL, timeout=20)
        self._now = now
        # installation id → (token, thời điểm hết hạn tính bằng giây)
        self._tokens: dict[int, tuple[str, float]] = {}

    # ----- API dùng ở nơi khác -----

    def list_repositories(self) -> list[RepoInfo]:
        repos: list[RepoInfo] = []
        for installation in self._get(self._app_jwt(), "/app/installations"):
            token = self._installation_token(int(installation["id"]))
            for page in self._get_pages(token, "/installation/repositories?per_page=100"):
                repos.extend(RepoInfo.model_validate(repo) for repo in page["repositories"])
        return sorted(repos, key=lambda repo: repo.full_name)

    def list_branches(self, repo_full_name: str) -> list[str]:
        installation = self._get(self._app_jwt(), f"/repos/{repo_full_name}/installation")
        token = self._installation_token(int(installation["id"]))
        names: list[str] = []
        for page in self._get_pages(token, f"/repos/{repo_full_name}/branches?per_page=100"):
            names.extend(branch["name"] for branch in page)
        return sorted(names)

    def _repo_token(self, repo_full_name: str) -> str:
        installation = self._get(self._app_jwt(), f"/repos/{repo_full_name}/installation")
        return self._installation_token(int(installation["id"]))

    @staticmethod
    def _issue(data: dict[str, Any]) -> IssueInfo:
        return IssueInfo(
            number=data["number"],
            url=data["html_url"],
            state=data["state"],
            title=data["title"],
            labels=[label["name"] for label in data["labels"]],
        )

    def find_issue_by_label(self, repo_full_name: str, label: str) -> IssueInfo | None:
        token = self._repo_token(repo_full_name)
        url = f"/repos/{repo_full_name}/issues"
        issues: list[IssueInfo] = []
        for page in self._get_pages(token, f"{url}?labels={label}&state=all&per_page=100"):
            issues.extend(self._issue(item) for item in page if "pull_request" not in item)
        return min(issues, key=lambda issue: issue.number) if issues else None

    def create_issue(
        self, repo_full_name: str, *, title: str, body: str, labels: list[str]
    ) -> IssueInfo:
        response = self._request(
            "POST",
            self._repo_token(repo_full_name),
            f"/repos/{repo_full_name}/issues",
            json={"title": title, "body": body, "labels": labels},
        )
        return self._issue(response.json())

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
        response = self._request(
            "PATCH",
            self._repo_token(repo_full_name),
            f"/repos/{repo_full_name}/issues/{number}",
            json={"title": title, "body": body, "labels": labels, "state": state},
        )
        return self._issue(response.json())

    def ensure_label(self, repo_full_name: str, name: str, *, color: str | None = None) -> None:
        token = self._repo_token(repo_full_name)
        url = f"/repos/{repo_full_name}/labels"
        try:
            payload: dict[str, str] = {"name": name}
            if color:
                payload["color"] = color
            self._request("POST", token, url, json=payload)
        except GitHubError as error:
            if "already_exists" not in str(error):
                raise

    def list_issue_comments(self, repo_full_name: str, issue_number: int) -> list[IssueComment]:
        token = self._repo_token(repo_full_name)
        url = f"/repos/{repo_full_name}/issues/{issue_number}/comments?per_page=100"
        comments: list[IssueComment] = []
        for page in self._get_pages(token, url):
            comments.extend(IssueComment(id=item["id"], body=item.get("body", "")) for item in page)
        return comments

    def create_issue_comment(self, repo_full_name: str, issue_number: int, body: str) -> None:
        self._request(
            "POST",
            self._repo_token(repo_full_name),
            f"/repos/{repo_full_name}/issues/{issue_number}/comments",
            json={"body": body},
        )

    def update_issue_comment(self, repo_full_name: str, comment_id: int, body: str) -> None:
        self._request(
            "PATCH",
            self._repo_token(repo_full_name),
            f"/repos/{repo_full_name}/issues/comments/{comment_id}",
            json={"body": body},
        )

    def update_issue_state_and_labels(
        self,
        repo_full_name: str,
        issue_number: int,
        *,
        state: Literal["open", "closed"],
        labels: list[str],
    ) -> None:
        self._request(
            "PATCH",
            self._repo_token(repo_full_name),
            f"/repos/{repo_full_name}/issues/{issue_number}",
            json={"state": state, "labels": labels},
        )

    def add_assignees(
        self, repo_full_name: str, issue_number: int, assignees: list[str]
    ) -> None:
        """Giao issue cho người khác. GitHub trả 201 dù bỏ qua người không hợp lệ,
        nên phải so danh sách `assignees` trong phản hồi với danh sách đã gửi."""
        response = self._request(
            "POST",
            self._repo_token(repo_full_name),
            f"/repos/{repo_full_name}/issues/{issue_number}/assignees",
            json={"assignees": assignees},
        )
        assigned = {user["login"].casefold() for user in response.json().get("assignees", [])}
        for name in assignees:
            if name.casefold() not in assigned:
                raise GitHubError(f"Không gán được @{name}")

    # ----- Xác thực -----

    def _app_jwt(self) -> str:
        issued_at = int(self._now()) - 60  # lùi 60 giây phòng đồng hồ máy lệch
        payload = {"iat": issued_at, "exp": issued_at + 600, "iss": self._app_id}
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def _installation_token(self, installation_id: int) -> str:
        cached = self._tokens.get(installation_id)
        if cached and cached[1] - TOKEN_SAFETY_SECONDS > self._now():
            return cached[0]

        response = self._request(
            "POST", self._app_jwt(), f"/app/installations/{installation_id}/access_tokens"
        )
        data = response.json()
        expires_at = datetime.fromisoformat(data["expires_at"]).timestamp()
        self._tokens[installation_id] = (data["token"], expires_at)
        return str(data["token"])

    # ----- Gửi request -----

    def _request(
        self, method: str, bearer: str, url: str, *, json: dict[str, Any] | None = None
    ) -> httpx.Response:
        headers = {**HEADERS, "Authorization": f"Bearer {bearer}"}
        try:
            response = self._http.request(method, url, headers=headers, json=json)
        except httpx.HTTPError as error:
            raise GitHubError(f"Không kết nối được GitHub: {error}") from error
        if response.status_code >= 400:
            if response.status_code in (403, 429):
                raise GitHubError(f"GitHub bị giới hạn lượt gọi ({response.status_code})")
            if response.status_code == 422:
                errors = response.json().get("errors", [])
                if any(item.get("code") == "already_exists" for item in errors):
                    raise GitHubError("GitHub trả lỗi 422: already_exists")
            raise GitHubError(f"GitHub trả lỗi {response.status_code} khi gọi {url}")
        return response

    def _get(self, bearer: str, url: str) -> Any:
        return self._request("GET", bearer, url).json()

    def _get_pages(self, bearer: str, url: str) -> list[Any]:
        """GitHub chia kết quả thành nhiều trang; đi theo link `rel="next"` tới hết."""
        pages: list[Any] = []
        next_url: str | None = url
        while next_url:
            response = self._request("GET", bearer, next_url)
            pages.append(response.json())
            next_url = response.links.get("next", {}).get("url")
        return pages

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
from typing import Any, Protocol

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


class GitHubNotConfiguredError(Exception):
    pass


class GitHubError(Exception):
    """GitHub trả lỗi (sai khoá, App chưa được cài, hết quota...)."""


class GitHubClient(Protocol):
    def list_repositories(self) -> list[RepoInfo]: ...

    def list_branches(self, repo_full_name: str) -> list[str]: ...


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

    def _request(self, method: str, bearer: str, url: str) -> httpx.Response:
        headers = {**HEADERS, "Authorization": f"Bearer {bearer}"}
        try:
            response = self._http.request(method, url, headers=headers)
        except httpx.HTTPError as error:
            raise GitHubError(f"Không kết nối được GitHub: {error}") from error
        if response.status_code >= 400:
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

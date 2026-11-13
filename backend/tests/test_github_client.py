"""Test GitHubAppClient với một "GitHub giả" (httpx.MockTransport), không gọi mạng."""

import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.github.client import GitHubAppClient, GitHubError, normalize_private_key

APP_ID = "12345"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
PUBLIC_PEM = _KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

NOW = 1_800_000_000.0


class FakeGitHubServer:
    """Trả lời như GitHub REST API cho vài đường dẫn cần dùng."""

    def __init__(self) -> None:
        self.token_requests: list[str] = []
        self.auth_headers: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.auth_headers.append(request.headers.get("Authorization", ""))
        path, query = request.url.path, request.url.query.decode()

        if path == "/app/installations":
            return httpx.Response(200, json=[{"id": 1}, {"id": 2}])
        if path.startswith("/app/installations/") and path.endswith("/access_tokens"):
            installation = path.split("/")[3]
            self.token_requests.append(installation)
            return httpx.Response(
                201, json={"token": f"token-{installation}", "expires_at": "2027-01-15T09:00:00Z"}
            )
        if path == "/installation/repositories":
            token = request.headers["Authorization"].removeprefix("Bearer ")
            return self._repositories(token, query)
        if path == "/repos/org/web/installation":
            return httpx.Response(200, json={"id": 1})
        if path == "/repos/org/web/branches":
            return httpx.Response(200, json=[{"name": "main"}, {"name": "develop"}])
        return httpx.Response(404, json={"message": "Not Found"})

    @staticmethod
    def _repositories(token: str, query: str) -> httpx.Response:
        def repo(name: str) -> dict[str, object]:
            return {"full_name": name, "default_branch": "main", "private": True}

        if token == "token-1" and "page=2" not in query:
            next_url = "https://api.github.com/installation/repositories?per_page=100&page=2"
            next_link = f'<{next_url}>; rel="next"'
            return httpx.Response(
                200,
                json={"repositories": [repo("org/web")]},
                headers={"Link": next_link},
            )
        if token == "token-1":
            return httpx.Response(200, json={"repositories": [repo("org/api")]})
        return httpx.Response(200, json={"repositories": [repo("other/app")]})


def make_client(server: FakeGitHubServer) -> GitHubAppClient:
    http = httpx.Client(transport=httpx.MockTransport(server), base_url="https://api.github.com")
    return GitHubAppClient(APP_ID, PRIVATE_PEM, http=http, now=lambda: NOW)


def test_lists_repositories_across_installations_and_pages() -> None:
    client = make_client(FakeGitHubServer())

    repos = client.list_repositories()

    assert [repo.full_name for repo in repos] == ["org/api", "org/web", "other/app"]
    assert repos[0].default_branch == "main"


def test_installation_token_is_reused_until_expiry() -> None:
    server = FakeGitHubServer()
    client = make_client(server)

    client.list_repositories()
    client.list_repositories()

    assert sorted(server.token_requests) == ["1", "2"]


def test_list_branches_uses_repo_installation() -> None:
    client = make_client(FakeGitHubServer())

    assert client.list_branches("org/web") == ["develop", "main"]


def test_jwt_is_signed_with_app_id() -> None:
    server = FakeGitHubServer()
    make_client(server).list_repositories()

    app_jwt = server.auth_headers[0].removeprefix("Bearer ")
    # Test dùng thời gian giả (năm 2027) nên bỏ kiểm tra hạn của JWT
    claims = jwt.decode(
        app_jwt,
        PUBLIC_PEM,
        algorithms=["RS256"],
        options={"verify_exp": False, "verify_iat": False},
    )

    assert claims["iss"] == APP_ID
    assert claims["iat"] == int(NOW) - 60


def test_normalize_private_key_converts_escaped_newlines() -> None:
    one_line = PRIVATE_PEM.replace("\n", "\\n")

    assert normalize_private_key(f"'{one_line}'") == PRIVATE_PEM.strip()


def test_http_error_becomes_github_error() -> None:
    def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=json.dumps({"message": "Bad credentials"}))

    http = httpx.Client(transport=httpx.MockTransport(unauthorized), base_url="https://api.github.com")
    client = GitHubAppClient(APP_ID, PRIVATE_PEM, http=http, now=lambda: NOW)

    with pytest.raises(GitHubError, match="401"):
        client.list_repositories()

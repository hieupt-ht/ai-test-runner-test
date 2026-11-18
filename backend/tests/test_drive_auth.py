"""Script lấy refresh token Drive: đúng tham số xin quyền, không in client secret."""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.tools.drive_auth import AuthError, build_auth_url, exchange_code, main

REDIRECT = "http://localhost:8765"


def client_with(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler)


def test_auth_url_asks_offline_access_with_drive_file_scope() -> None:
    query = parse_qs(urlparse(build_auth_url("my-id", REDIRECT)).query)

    assert query["client_id"] == ["my-id"]
    assert query["redirect_uri"] == [REDIRECT]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["https://www.googleapis.com/auth/drive.file"]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]


def test_exchange_code_returns_refresh_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r-token"})

    http = client_with(httpx.MockTransport(handler))

    token = exchange_code("the-code", "my-id", "my-secret", REDIRECT, http)

    assert token == "r-token"
    body = parse_qs(seen[0].content.decode())
    assert body["code"] == ["the-code"] and body["grant_type"] == ["authorization_code"]


def test_exchange_code_without_refresh_token_explains_what_to_do() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"access_token": "a"}))

    with pytest.raises(AuthError, match="refresh token"):
        exchange_code("c", "my-id", "my-secret", REDIRECT, client_with(transport))


def test_exchange_code_error_does_not_leak_secret() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(400, json={"error": "invalid_grant"}))

    with pytest.raises(AuthError) as caught:
        exchange_code("c", "my-id", "my-secret", REDIRECT, client_with(transport))

    assert "my-secret" not in str(caught.value)


def test_main_requires_client_id_and_secret(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)

    assert main(env_file=None) == 2
    assert "GOOGLE_OAUTH_CLIENT_ID" in capsys.readouterr().err

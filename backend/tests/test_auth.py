from authlib.integrations.base_client.errors import OAuthError
from fastapi.testclient import TestClient

from app.api.oauth import GoogleIdentity
from app.core.models.user import Role
from app.core.repositories.users import UserRepository
from tests.conftest import make_user
from tests.fakes import FakeOAuth


def log_in(client: TestClient, oauth: FakeOAuth, email: str) -> None:
    oauth.identity = GoogleIdentity(email=email, name="Ai đó")
    response = client.get("/api/auth/callback")
    assert response.headers["location"] == "/"


def test_login_redirects_to_google(client: TestClient) -> None:
    response = client.get("/api/auth/login")

    assert response.status_code in (302, 307)
    assert response.headers["location"].startswith("https://accounts.google.com/")


def test_callback_allowed_user_sets_cookie_and_redirects_home(
    client: TestClient, users: UserRepository, oauth: FakeOAuth
) -> None:
    users.create(make_user("an@x.com"))
    oauth.identity = GoogleIdentity(email="  An@X.com", name="An")

    response = client.get("/api/auth/callback")

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"
    set_cookie = response.headers["set-cookie"]
    assert "atr_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()


def test_callback_unknown_email_redirects_to_login_error(
    client: TestClient, oauth: FakeOAuth
) -> None:
    oauth.identity = GoogleIdentity(email="la@x.com", name="Lạ")

    response = client.get("/api/auth/callback")

    assert response.headers["location"] == "/login?error=not_allowed"
    assert "atr_session=" not in response.headers.get("set-cookie", "")


def test_callback_inactive_user_rejected(
    client: TestClient, users: UserRepository, oauth: FakeOAuth
) -> None:
    users.create(make_user("an@x.com", active=False))
    oauth.identity = GoogleIdentity(email="an@x.com", name="An")

    response = client.get("/api/auth/callback")

    assert response.headers["location"] == "/login?error=not_allowed"


def test_me_without_cookie_is_401(client: TestClient) -> None:
    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Bạn cần đăng nhập"}


def test_me_returns_user(client: TestClient, users: UserRepository, oauth: FakeOAuth) -> None:
    users.create(make_user("an@x.com", role=Role.QA_LEAD, name="An"))
    log_in(client, oauth, "an@x.com")

    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["email"] == "an@x.com"
    assert response.json()["role"] == "QA_LEAD"


def test_user_deactivated_after_login_gets_401_next_request(
    client: TestClient, users: UserRepository, oauth: FakeOAuth
) -> None:
    users.create(make_user("an@x.com"))
    log_in(client, oauth, "an@x.com")

    users.update(make_user("an@x.com", active=False))

    assert client.get("/api/me").status_code == 401


def test_logout_deletes_session(
    client: TestClient, users: UserRepository, oauth: FakeOAuth
) -> None:
    users.create(make_user("an@x.com"))
    log_in(client, oauth, "an@x.com")
    session_id = client.cookies["atr_session"]

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    client.cookies.set("atr_session", session_id)  # thử dùng lại session cũ
    assert client.get("/api/me").status_code == 401


def test_callback_oauth_error_redirects_to_login_error(
    client: TestClient, oauth: FakeOAuth
) -> None:
    oauth.fail_with = OAuthError(error="access_denied")  # người dùng bấm Huỷ ở Google

    response = client.get("/api/auth/callback?error=access_denied")

    assert response.headers["location"] == "/login?error=oauth_failed"

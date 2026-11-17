from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.user import Role
from app.core.passwords import hash_password
from app.core.repositories.users import UserRepository
from tests.conftest import make_user

PASSWORD = "mat-khau-1"
GENERIC_ERROR = {"detail": "Email hoặc mật khẩu không đúng"}


def add_user(users: UserRepository, email: str = "an@x.com", **kwargs: object) -> None:
    users.create(make_user(email, **kwargs), password_hash=hash_password(PASSWORD))  # type: ignore[arg-type]


def login(client: TestClient, email: str, password: str = PASSWORD):  # type: ignore[no-untyped-def]
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_success_sets_cookie(client: TestClient, users: UserRepository) -> None:
    add_user(users)

    response = login(client, "an@x.com")

    assert response.status_code == 200
    assert response.json()["email"] == "an@x.com"
    set_cookie = response.headers["set-cookie"]
    assert "atr_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()


def test_login_normalizes_email(client: TestClient, users: UserRepository) -> None:
    add_user(users)

    assert login(client, "  An@X.com ").status_code == 200


def test_login_wrong_password_401_generic(client: TestClient, users: UserRepository) -> None:
    add_user(users)

    response = login(client, "an@x.com", "sai-mat-khau")

    assert response.status_code == 401
    assert response.json() == GENERIC_ERROR
    assert "atr_session=" not in response.headers.get("set-cookie", "")


def test_login_unknown_email_same_response_as_wrong_password(
    client: TestClient, users: UserRepository
) -> None:
    add_user(users)

    wrong = login(client, "an@x.com", "sai-mat-khau")
    unknown = login(client, "la@x.com", "sai-mat-khau")

    assert (unknown.status_code, unknown.json()) == (wrong.status_code, wrong.json())


def test_login_inactive_user_401_generic(client: TestClient, users: UserRepository) -> None:
    add_user(users, active=False)

    response = login(client, "an@x.com")

    assert (response.status_code, response.json()) == (401, GENERIC_ERROR)


def test_login_user_without_password_401_generic(client: TestClient, users: UserRepository) -> None:
    users.create(make_user("an@x.com"))

    for password in ("", PASSWORD):
        response = login(client, "an@x.com", password)
        assert (response.status_code, response.json()) == (401, GENERIC_ERROR)


def test_login_locked_after_5_failures_429(client: TestClient, users: UserRepository) -> None:
    add_user(users)
    for _ in range(5):
        assert login(client, "an@x.com", "sai-mat-khau").status_code == 401

    response = login(client, "an@x.com")  # đúng mật khẩu nhưng đã bị khoá

    assert response.status_code == 429
    assert response.json() == {
        "detail": "Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút"
    }


def test_login_unknown_email_is_locked_too(client: TestClient) -> None:
    for _ in range(5):
        login(client, "la@x.com", "sai-mat-khau")

    assert login(client, "la@x.com").status_code == 429


def test_login_success_resets_counter(client: TestClient, users: UserRepository) -> None:
    add_user(users)
    for _ in range(4):
        login(client, "an@x.com", "sai-mat-khau")
    assert login(client, "an@x.com").status_code == 200
    for _ in range(4):
        login(client, "an@x.com", "sai-mat-khau")

    assert login(client, "an@x.com").status_code == 200


def test_me_without_cookie_is_401(client: TestClient) -> None:
    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Bạn cần đăng nhập"}


def test_me_returns_user_without_hash(client: TestClient, users: UserRepository) -> None:
    add_user(users, role=Role.QA_LEAD, name="An")
    login(client, "an@x.com")

    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["email"] == "an@x.com"
    assert response.json()["role"] == "QA_LEAD"
    assert "password" not in response.text


def test_login_response_has_no_hash(client: TestClient, users: UserRepository) -> None:
    add_user(users)

    response = login(client, "an@x.com")

    assert "argon2" not in response.text
    assert "password" not in response.text


def test_user_deactivated_after_login_gets_401_next_request(
    client: TestClient, users: UserRepository
) -> None:
    add_user(users)
    login(client, "an@x.com")

    users.update(make_user("an@x.com", active=False))

    assert client.get("/api/me").status_code == 401


def test_logout_deletes_session(client: TestClient, users: UserRepository) -> None:
    add_user(users)
    login(client, "an@x.com")
    session_id = client.cookies["atr_session"]

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    client.cookies.set("atr_session", session_id)  # thử dùng lại session cũ
    assert client.get("/api/me").status_code == 401


def test_old_oauth_routes_are_gone(client: TestClient) -> None:
    assert client.get("/api/auth/callback").status_code == 404
    assert client.get("/api/auth/login").status_code == 405


# ---- Đổi mật khẩu ----

NEW_PASSWORD = "mat-khau-moi-2"


def change(client: TestClient, current: str = PASSWORD, new: str = NEW_PASSWORD):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/auth/change-password", json={"current_password": current, "new_password": new}
    )


def test_change_password_success_old_password_stops_working(
    client: TestClient, app: FastAPI, users: UserRepository
) -> None:
    add_user(users)
    login(client, "an@x.com")

    assert change(client).status_code == 204

    fresh = TestClient(app, follow_redirects=False)
    assert login(fresh, "an@x.com", PASSWORD).status_code == 401
    assert login(fresh, "an@x.com", NEW_PASSWORD).status_code == 200


def test_change_password_keeps_current_browser_logged_in(
    client: TestClient, users: UserRepository
) -> None:
    add_user(users)
    login(client, "an@x.com")

    response = change(client)

    assert "atr_session=" in response.headers["set-cookie"]
    assert client.get("/api/me").status_code == 200


def test_change_password_logs_out_other_browsers(
    client: TestClient, app: FastAPI, users: UserRepository
) -> None:
    add_user(users)
    login(client, "an@x.com")
    other = TestClient(app, follow_redirects=False)
    login(other, "an@x.com")

    change(client)

    assert other.get("/api/me").status_code == 401
    assert client.get("/api/me").status_code == 200


def test_change_password_wrong_current_400(client: TestClient, users: UserRepository) -> None:
    add_user(users)
    login(client, "an@x.com")

    response = change(client, current="sai-roi-nhe")

    assert response.status_code == 400
    assert response.json() == {"detail": "Mật khẩu hiện tại không đúng"}
    assert login(TestClient(client.app), "an@x.com", PASSWORD).status_code == 200  # type: ignore[arg-type]


def test_change_password_wrong_current_counts_toward_lock(
    client: TestClient, users: UserRepository
) -> None:
    add_user(users)
    login(client, "an@x.com")

    for _ in range(5):
        assert change(client, current="sai-roi-nhe").status_code == 400

    assert change(client).status_code == 429  # bị khoá, đúng mật khẩu cũng không được


def test_change_password_short_new_422(client: TestClient, users: UserRepository) -> None:
    add_user(users)
    login(client, "an@x.com")

    assert change(client, new="ngan").status_code == 422
    assert change(client, new="a" * 129).status_code == 422
    assert login(TestClient(client.app), "an@x.com", PASSWORD).status_code == 200  # type: ignore[arg-type]


def test_change_password_requires_login_401(client: TestClient) -> None:
    assert change(client).status_code == 401

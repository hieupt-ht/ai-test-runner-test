import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.repositories.users import UserRepository
from tests.conftest import SYSTEM_SHEET_ID, make_user
from tests.fakes import FakeSheetsGateway


def audit_rows(gateway: FakeSheetsGateway) -> list[list[str]]:
    return gateway.data[SYSTEM_SHEET_ID]["AuditLog"][1:]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/users", None),
        (
            "POST",
            "/api/users",
            {"email": "b@x.com", "name": "B", "role": "TESTER", "password": "mat-khau-1"},
        ),
        ("PATCH", "/api/users/lead@x.com", {"name": "Đổi tên"}),
    ],
)
def test_non_admin_gets_403(
    client_as_qa_lead: TestClient, method: str, path: str, body: dict[str, str] | None
) -> None:
    response = client_as_qa_lead.request(method, path, json=body)

    assert response.status_code == 403
    assert response.json() == {"detail": "Bạn không có quyền thực hiện thao tác này"}


def test_list_users(client_as_admin: TestClient, users: UserRepository) -> None:
    users.create(make_user("an@x.com"))

    response = client_as_admin.get("/api/users")

    assert response.status_code == 200
    assert {user["email"] for user in response.json()} == {"admin@x.com", "an@x.com"}


def test_create_user_normalizes_email_and_audits(
    client_as_admin: TestClient, gateway: FakeSheetsGateway
) -> None:
    response = client_as_admin.post(
        "/api/users",
        json={"email": "  Binh@X.com ", "name": "Bình", "role": "TESTER", "password": "mat-khau-1"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "binh@x.com"
    assert response.json()["active"] is True
    rows = audit_rows(gateway)
    assert len(rows) == 1
    assert rows[0][1:5] == ["admin@x.com", "CREATE", "user", "binh@x.com"]


def test_create_duplicate_is_409(client_as_admin: TestClient, users: UserRepository) -> None:
    users.create(make_user("an@x.com"))

    response = client_as_admin.post(
        "/api/users",
        json={"email": "AN@x.com", "name": "An", "role": "TESTER", "password": "mat-khau-1"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email này đã có trong hệ thống"}


@pytest.mark.parametrize(
    "body",
    [
        {"email": "khong-phai-email", "name": "An", "role": "TESTER", "password": "mat-khau-1"},
        {"email": "an@x.com", "name": "", "role": "TESTER", "password": "mat-khau-1"},
        {"email": "an@x.com", "name": "An", "role": "SUPERMAN", "password": "mat-khau-1"},
    ],
)
def test_create_invalid_input_is_422(client_as_admin: TestClient, body: dict[str, str]) -> None:
    assert client_as_admin.post("/api/users", json=body).status_code == 422


def test_patch_role_and_deactivate(
    client_as_admin: TestClient, users: UserRepository, gateway: FakeSheetsGateway
) -> None:
    users.create(make_user("an@x.com", name="An"))

    response = client_as_admin.patch(
        "/api/users/an@x.com", json={"role": "QA_LEAD", "active": False, "name": "An"}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "QA_LEAD"
    assert response.json()["active"] is False
    diff = json.loads(audit_rows(gateway)[-1][5])
    assert diff == {"role": ["TESTER", "QA_LEAD"], "active": [True, False]}


@pytest.mark.parametrize("body", [{"active": False}, {"role": "QA_LEAD"}])
def test_admin_cannot_deactivate_or_demote_self(
    client_as_admin: TestClient, body: dict[str, object]
) -> None:
    response = client_as_admin.patch("/api/users/admin@x.com", json=body)

    assert response.status_code == 400
    assert response.json() == {"detail": "Bạn không thể tự khoá hoặc tự hạ quyền của chính mình"}


def test_admin_can_rename_self(client_as_admin: TestClient) -> None:
    response = client_as_admin.patch("/api/users/ADMIN@x.com", json={"name": "Quản trị"})

    assert response.status_code == 200
    assert response.json()["name"] == "Quản trị"


def test_patch_unknown_user_is_404(client_as_admin: TestClient) -> None:
    response = client_as_admin.patch("/api/users/khong-co@x.com", json={"name": "X"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Không tìm thấy người dùng"}


def _create(client: TestClient, password: str | None, email: str = "binh@x.com") -> int:
    body: dict[str, str] = {"email": email, "name": "Bình", "role": "TESTER"}
    if password is not None:
        body["password"] = password
    return client.post("/api/users", json=body).status_code


def test_create_user_with_password_can_log_in(client_as_admin: TestClient, app: FastAPI) -> None:
    assert _create(client_as_admin, "Mật khẩu 123 ") == 201

    other = TestClient(app, follow_redirects=False)
    response = other.post(
        "/api/auth/login", json={"email": "binh@x.com", "password": "Mật khẩu 123 "}
    )
    assert response.status_code == 200


def test_create_user_requires_password_422(client_as_admin: TestClient) -> None:
    assert _create(client_as_admin, None) == 422


@pytest.mark.parametrize("password", ["", "ngan", "1234567"])
def test_short_password_422_and_nothing_saved(
    client_as_admin: TestClient, users: UserRepository, password: str
) -> None:
    assert _create(client_as_admin, password) == 422
    assert users.get("binh@x.com") is None


def test_too_long_password_422(client_as_admin: TestClient, users: UserRepository) -> None:
    assert _create(client_as_admin, "a" * 129) == 422
    assert users.get("binh@x.com") is None


def test_response_has_no_hash_or_password(client_as_admin: TestClient) -> None:
    response = client_as_admin.post(
        "/api/users",
        json={"email": "binh@x.com", "name": "B", "role": "TESTER", "password": "mat-khau-1"},
    )

    text = response.text
    assert "password" not in text
    assert "argon2" not in text
    assert "mat-khau-1" not in text


def test_audit_log_has_no_password_or_hash(
    client_as_admin: TestClient, gateway: FakeSheetsGateway
) -> None:
    _create(client_as_admin, "mat-khau-1")

    row = " ".join(audit_rows(gateway)[-1])
    assert "password" not in row
    assert "argon2" not in row
    assert "mat-khau-1" not in row


# ---- Đặt lại mật khẩu ----

RESET_BODY = {"password": "mat-khau-moi-2"}


def test_reset_password_admin_only_403_for_tester(
    client_as_tester: TestClient, users: UserRepository
) -> None:
    users.create(make_user("an@x.com"))

    response = client_as_tester.post("/api/users/an@x.com/reset-password", json=RESET_BODY)

    assert response.status_code == 403


def test_reset_password_logs_out_target_and_new_password_works(
    client_as_admin: TestClient, app: FastAPI, users: UserRepository
) -> None:
    from app.core.models.user import Role
    from tests.conftest import log_in_as

    target = TestClient(app, follow_redirects=False)
    log_in_as(target, users, "an@x.com", Role.TESTER)

    response = client_as_admin.post("/api/users/an@x.com/reset-password", json=RESET_BODY)

    assert response.status_code == 204
    assert target.get("/api/me").status_code == 401
    fresh = TestClient(app, follow_redirects=False)
    ok = fresh.post("/api/auth/login", json={"email": "an@x.com", **{"password": "mat-khau-moi-2"}})
    assert ok.status_code == 200


def test_reset_password_unknown_user_404(client_as_admin: TestClient) -> None:
    response = client_as_admin.post("/api/users/khong-co@x.com/reset-password", json=RESET_BODY)

    assert response.status_code == 404
    assert response.json() == {"detail": "Không tìm thấy người dùng"}


def test_reset_password_short_422(client_as_admin: TestClient, users: UserRepository) -> None:
    users.create(make_user("an@x.com"))

    response = client_as_admin.post("/api/users/an@x.com/reset-password", json={"password": "ngan"})

    assert response.status_code == 422


def test_reset_own_password_as_admin_works(client_as_admin: TestClient, app: FastAPI) -> None:
    response = client_as_admin.post("/api/users/admin@x.com/reset-password", json=RESET_BODY)

    assert response.status_code == 204
    assert client_as_admin.get("/api/me").status_code == 401  # session cũ đã bị xoá
    fresh = TestClient(app, follow_redirects=False)
    ok = fresh.post("/api/auth/login", json={"email": "admin@x.com", "password": "mat-khau-moi-2"})
    assert ok.status_code == 200


def test_reset_password_for_inactive_user_still_cannot_log_in(
    client_as_admin: TestClient, app: FastAPI, users: UserRepository
) -> None:
    users.create(make_user("an@x.com", active=False))

    assert (
        client_as_admin.post("/api/users/an@x.com/reset-password", json=RESET_BODY).status_code
        == 204
    )

    fresh = TestClient(app, follow_redirects=False)
    response = fresh.post(
        "/api/auth/login", json={"email": "an@x.com", "password": "mat-khau-moi-2"}
    )
    assert response.status_code == 401


def test_reset_password_audit_has_no_password(
    client_as_admin: TestClient, users: UserRepository, gateway: FakeSheetsGateway
) -> None:
    users.create(make_user("an@x.com"))

    client_as_admin.post("/api/users/an@x.com/reset-password", json=RESET_BODY)

    row = audit_rows(gateway)[-1]
    assert row[1:5] == ["admin@x.com", "RESET_PASSWORD", "user", "an@x.com"]
    text = " ".join(row)
    assert "mat-khau-moi-2" not in text
    assert "argon2" not in text

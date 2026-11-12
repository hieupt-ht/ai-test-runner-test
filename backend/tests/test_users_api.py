import json

import pytest
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
        ("POST", "/api/users", {"email": "b@x.com", "name": "B", "role": "TESTER"}),
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
        "/api/users", json={"email": "  Binh@X.com ", "name": "Bình", "role": "TESTER"}
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
        "/api/users", json={"email": "AN@x.com", "name": "An", "role": "TESTER"}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email này đã có trong hệ thống"}


@pytest.mark.parametrize(
    "body",
    [
        {"email": "khong-phai-email", "name": "An", "role": "TESTER"},
        {"email": "an@x.com", "name": "", "role": "TESTER"},
        {"email": "an@x.com", "name": "An", "role": "SUPERMAN"},
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
    assert response.json() == {
        "detail": "Bạn không thể tự khoá hoặc tự hạ quyền của chính mình"
    }


def test_admin_can_rename_self(client_as_admin: TestClient) -> None:
    response = client_as_admin.patch("/api/users/ADMIN@x.com", json={"name": "Quản trị"})

    assert response.status_code == 200
    assert response.json()["name"] == "Quản trị"


def test_patch_unknown_user_is_404(client_as_admin: TestClient) -> None:
    response = client_as_admin.patch("/api/users/khong-co@x.com", json={"name": "X"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Không tìm thấy người dùng"}

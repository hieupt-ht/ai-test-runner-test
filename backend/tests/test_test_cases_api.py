import threading
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.models.project import Project
from app.core.models.test_case import TestCase
from app.core.models.user import Role
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.time import today_in_vietnam
from tests.conftest import client_for, make_project, make_user
from tests.fakes import FakeOAuth, FakeSheetsGateway

NEXT_WEEK = (today_in_vietnam() + timedelta(days=7)).isoformat()

BODY: dict[str, Any] = {
    "screen_id": "SC-0001",
    "title": "Đăng nhập thành công",
    "steps": [{"action": "Nhập email và mật khẩu", "expected": "Vào trang chủ"}],
    "expected_result": "Đăng nhập được",
    "severity": "HIGH",
    "priority": "P1",
}


@pytest.fixture
def project(
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    users: UserRepository,
) -> Project:
    for user in (
        make_user("an@x.com", role=Role.TESTER, name="An"),
        make_user("binh@x.com", role=Role.TESTER, name="Bình"),
        make_user("viewer@x.com", role=Role.VIEWER),
    ):
        if users.get(user.email) is None:
            users.create(user)
    return make_project(
        projects,
        members,
        gateway,
        member_emails=("lead@x.com", "an@x.com", "binh@x.com", "viewer@x.com"),
    )


@pytest.fixture
def lead(app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project) -> TestClient:
    """QA Lead; đã tạo màn hình SC-0001 và giao cho An và Bình."""
    browser = client_for(app, oauth, users, "lead@x.com", Role.QA_LEAD)
    browser.post(f"/api/projects/{project.id}/screens", json={"name": "Đăng nhập"})
    browser.post(
        f"/api/projects/{project.id}/assignments",
        json={
            "screen_id": "SC-0001",
            "assignee_emails": ["an@x.com", "binh@x.com"],
            "deadline": NEXT_WEEK,
        },
    )
    return browser


@pytest.fixture
def an(app: FastAPI, oauth: FakeOAuth, users: UserRepository, lead: TestClient) -> TestClient:
    return client_for(app, oauth, users, "an@x.com", Role.TESTER)


@pytest.fixture
def binh(app: FastAPI, oauth: FakeOAuth, users: UserRepository, lead: TestClient) -> TestClient:
    return client_for(app, oauth, users, "binh@x.com", Role.TESTER)


def url(project: Project, suffix: str = "") -> str:
    return f"/api/projects/{project.id}/test-cases{suffix}"


class RecordingIssueSink:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.fail = fail

    def sync_case(self, project: Project, case: TestCase, *, screen_name: str = "") -> None:
        self.calls.append((case.id, case.status.value, screen_name))
        if self.fail:
            raise RuntimeError("GitHub giả bị lỗi")


def test_approve_syncs_issue_for_saved_case(
    app: FastAPI, an: TestClient, lead: TestClient, project: Project
) -> None:
    sink = RecordingIssueSink()
    app.state.services.issue_sync = sink
    case = create(an, project).json()
    an.post(url(project, f"/{case['id']}/submit"), json={"version": 1})
    response = lead.post(url(project, f"/{case['id']}/approve"), json={"version": 2})
    assert response.status_code == 200
    assert sink.calls[-1] == (case["id"], "APPROVED", "Đăng nhập")


def test_batch_approve_syncs_only_approved_cases(
    app: FastAPI, an: TestClient, lead: TestClient, project: Project
) -> None:
    sink = RecordingIssueSink()
    app.state.services.issue_sync = sink
    first = create(an, project).json()
    skipped = create(an, project).json()
    an.post(url(project, f"/{first['id']}/submit"), json={"version": 1})
    sink.calls.clear()
    response = lead.post(
        url(project, "/approve-batch"),
        json={
            "items": [
                {"case_id": first["id"], "version": 2},
                {"case_id": skipped["id"], "version": 1},
            ]
        },
    )
    assert response.status_code == 200
    assert sink.calls == [(first["id"], "APPROVED", "Đăng nhập")]


def test_sync_failure_does_not_fail_save_or_duplicate_case(
    app: FastAPI, an: TestClient, project: Project
) -> None:
    sink = RecordingIssueSink(fail=True)
    app.state.services.issue_sync = sink
    created = create(an, project)
    assert created.status_code == 201
    assert len(an.get(url(project)).json()) == 1
    assert len(sink.calls) == 1


def test_edit_return_deprecate_and_restore_each_sync(
    app: FastAPI, an: TestClient, lead: TestClient, project: Project
) -> None:
    sink = RecordingIssueSink()
    app.state.services.issue_sync = sink
    case = create(an, project).json()
    path = url(project, f"/{case['id']}")
    an.post(f"{path}/submit", json={"version": 1})
    lead.post(f"{path}/approve", json={"version": 2})
    sink.calls.clear()

    edit = {key: value for key, value in BODY.items() if key != "screen_id"}
    assert an.put(path, json={**edit, "title": "Nội dung mới", "version": 3}).status_code == 200
    an.post(f"{path}/submit", json={"version": 4})
    lead.post(f"{path}/return", json={"version": 5, "comment": "Sửa lại"})
    an.post(f"{path}/deprecate", json={"version": 6})
    lead.post(f"{path}/restore", json={"version": 7})

    assert [status for _, status, _ in sink.calls] == [
        "DRAFT",
        "IN_REVIEW",
        "DRAFT",
        "DEPRECATED",
        "DRAFT",
    ]


def create(browser: TestClient, project: Project, **changes: Any) -> httpx.Response:
    response: httpx.Response = browser.post(url(project), json={**BODY, **changes})
    return response


def test_tester_creates_lists_and_reads_case(an: TestClient, project: Project) -> None:
    created = create(an, project)

    assert created.status_code == 201
    case = created.json()
    assert case["id"] == "TC-000001"
    assert case["status"] == "DRAFT"
    assert case["version"] == 1
    assert [c["id"] for c in an.get(url(project)).json()] == ["TC-000001"]

    detail = an.get(url(project, "/TC-000001"))
    assert detail.status_code == 200
    assert detail.json()["can_edit"] is True
    assert detail.json()["can_review"] is False
    assert an.get(url(project, "/TC-999999")).json() == {"detail": "Không tìm thấy test case"}


def test_two_people_save_same_version_second_gets_409(
    an: TestClient, binh: TestClient, project: Project
) -> None:
    create(an, project)
    edit = {k: v for k, v in BODY.items() if k != "screen_id"}

    first = an.put(url(project, "/TC-000001"), json={**edit, "title": "Bản của An", "version": 1})
    second = binh.put(
        url(project, "/TC-000001"), json={**edit, "title": "Bản của Bình", "version": 1}
    )

    assert first.status_code == 200
    assert first.json()["version"] == 2
    assert second.status_code == 409
    assert second.json()["detail"] == "Case này vừa được An cập nhật. Vui lòng tải lại."
    assert second.json()["latest"]["version"] == 2
    assert second.json()["latest"]["title"] == "Bản của An"


@pytest.mark.parametrize(
    "changes",
    [
        {"steps": []},
        {"steps": [{"action": "", "expected": ""}]},
        {"severity": "URGENT"},
        {"title": ""},
    ],
)
def test_validation_errors_are_422(
    an: TestClient, project: Project, changes: dict[str, Any]
) -> None:
    assert create(an, project, **changes).status_code == 422


def test_lead_returns_case_with_comment_and_history_shows_it(
    an: TestClient, lead: TestClient, project: Project
) -> None:
    create(an, project)
    assert an.post(url(project, "/TC-000001/submit"), json={"version": 1}).status_code == 200

    # Tester không có quyền trả lại.
    assert an.post(url(project, "/TC-000001/return"), json={"version": 2}).status_code == 403

    returned = lead.post(
        url(project, "/TC-000001/return"), json={"version": 2, "comment": "Thiếu bước kiểm tra"}
    )

    assert returned.status_code == 200
    assert returned.json()["status"] == "DRAFT"
    history = lead.get(url(project, "/TC-000001/history")).json()
    assert [entry["action"] for entry in history] == ["RETURN", "SUBMIT", "CREATE"]
    assert history[0]["diff"]["comment"] == "Thiếu bước kiểm tra"
    assert lead.get(url(project, "/TC-999999/history")).status_code == 404


def test_viewer_can_read_but_not_create(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, lead: TestClient, project: Project
) -> None:
    viewer = client_for(app, oauth, users, "viewer@x.com", Role.VIEWER)

    assert viewer.get(url(project)).status_code == 200
    forbidden = create(viewer, project)
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "Bạn không có quyền thực hiện thao tác này"}


def test_non_member_gets_404(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, project: Project
) -> None:
    stranger = client_for(app, oauth, users, "la@x.com", Role.TESTER)

    assert stranger.get(url(project)).status_code == 404
    assert create(stranger, project).status_code == 404


def test_archived_project_rejects_writes(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    an: TestClient,
    project: Project,
    projects: ProjectRepository,
) -> None:
    create(an, project)
    projects.update(project.model_copy(update={"archived": True}))
    # Thành viên thường không còn thấy dự án đã lưu trữ; Admin thấy nhưng không được ghi.
    admin = client_for(app, oauth, users, "admin@x.com", Role.ADMIN)

    assert admin.get(url(project)).status_code == 200
    response = admin.post(url(project, "/TC-000001/deprecate"), json={"version": 1})

    assert response.status_code == 409
    assert response.json() == {"detail": "Dự án đã được lưu trữ"}


def test_parallel_creates_via_api_get_distinct_ids(
    app: FastAPI, oauth: FakeOAuth, users: UserRepository, lead: TestClient, project: Project
) -> None:
    browsers = [
        client_for(app, oauth, users, "an@x.com", Role.TESTER),
        client_for(app, oauth, users, "binh@x.com", Role.TESTER),
    ]
    ids: list[str] = []
    failures: list[str] = []

    def worker(browser: TestClient) -> None:
        for _ in range(3):
            for _attempt in range(20):  # đụng khoá thì server báo "đang bận", thử lại
                response = create(browser, project)
                if response.status_code == 201:
                    ids.append(response.json()["id"])
                    break
            else:
                failures.append("hết số lần thử")

    threads = [threading.Thread(target=worker, args=(b,)) for b in browsers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not failures
    assert len(set(ids)) == 6
    assert len(lead.get(url(project)).json()) == 6


def test_archived_project_case_cannot_be_edited_or_reviewed(
    app: FastAPI,
    oauth: FakeOAuth,
    users: UserRepository,
    an: TestClient,
    project: Project,
    projects: ProjectRepository,
) -> None:
    create(an, project)
    projects.update(project.model_copy(update={"archived": True}))
    admin = client_for(app, oauth, users, "admin@x.com", Role.ADMIN)

    detail = admin.get(url(project, "/TC-000001")).json()

    assert detail["can_edit"] is False
    assert detail["can_review"] is False


def test_batch_approve_reports_approved_and_skipped(
    an: TestClient, lead: TestClient, project: Project
) -> None:
    create(an, project, title="Case 1")
    create(an, project, title="Case 2")
    an.post(url(project, "/TC-000001/submit"), json={"version": 1})
    an.post(url(project, "/TC-000002/submit"), json={"version": 1})

    response = lead.post(
        url(project, "/approve-batch"),
        json={
            "items": [
                {"case_id": "TC-000001", "version": 2},
                {"case_id": "TC-000002", "version": 1},  # version cũ
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [case["id"] for case in body["approved"]] == ["TC-000001"]
    assert [item["case_id"] for item in body["skipped"]] == ["TC-000002"]
    assert body["skipped"][0]["reason"]
    assert lead.get(url(project, "/TC-000001")).json()["status"] == "APPROVED"
    assert lead.get(url(project, "/TC-000002")).json()["status"] == "IN_REVIEW"


def test_batch_approve_forbidden_for_tester(an: TestClient, project: Project) -> None:
    create(an, project)

    response = an.post(
        url(project, "/approve-batch"), json={"items": [{"case_id": "TC-000001", "version": 1}]}
    )

    assert response.status_code == 403


def test_batch_approve_rejects_empty_list(lead: TestClient, project: Project) -> None:
    assert lead.post(url(project, "/approve-batch"), json={"items": []}).status_code == 422

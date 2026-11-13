"""Hai request chen nhau quanh tab Assignments (review M2: I-4).

Cách giả lập: request A đọc xong tab Assignments thì móc `after_next_read` chạy
ngay request B. Nếu A "kiểm tra" ngoài khoá, B sẽ lọt qua và dữ liệu bị sai.
Nếu A giữ khoá trong suốt "kiểm tra rồi ghi", B phải chờ khoá → LockTimeout.

Mỗi request dùng repository RIÊNG (như app thật: mỗi request dựng scope mới).
"""

from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta

import fakeredis
import pytest

from app.core.locks.redis_lock import LockTimeout
from app.core.models.project import Project
from app.core.models.user import Role
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.repositories.users import UserRepository
from app.core.services.assignments import AssignmentService
from app.core.services.members import MemberService
from app.core.services.screens import ScreenService
from app.core.time import today_in_vietnam
from tests.conftest import make_project, make_user
from tests.fakes import FakeSheetsGateway

LEAD = make_user("lead@x.com", role=Role.QA_LEAD)
TESTER = "tester@x.com"
NEXT_WEEK = today_in_vietnam() + timedelta(days=7)


class Request:
    """Dựng các repository/service cho MỘT request, giống scope_for trong app thật."""

    def __init__(
        self,
        gateway: FakeSheetsGateway,
        redis: fakeredis.FakeRedis,
        project: Project,
        members: ProjectMemberRepository,
        users: UserRepository,
    ) -> None:
        sheet = project.spreadsheet_id
        self.screens = ScreenRepository(gateway, sheet, redis, project.id, lock_wait_seconds=0.1)
        self.assignments = AssignmentRepository(
            gateway, sheet, redis, project.id, lock_wait_seconds=0.1
        )
        self.test_cases = TestCaseRepository(
            gateway, sheet, redis, project.id, lock_wait_seconds=0.1
        )
        audit = AuditLogRepository(gateway, sheet)
        self.assignment_service = AssignmentService(
            project_id=project.id,
            assignments=self.assignments,
            screens=self.screens,
            test_cases=self.test_cases,
            members=members,
            users=users,
            audit_log=audit,
        )
        self.member_service = MemberService(
            project_id=project.id,
            members=members,
            users=users,
            assignments=self.assignments,
            audit_log=audit,
        )
        self.screen_service = ScreenService(self.screens, self.assignments, self.test_cases, audit)

    def assign_tester(self) -> None:
        self.assignment_service.assign(
            LEAD, screen_id="SC-0001", assignee_emails=[TESTER], deadline=NEXT_WEEK
        )


@pytest.fixture
def new_request(
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    users: UserRepository,
) -> Callable[[], Request]:
    users.create(make_user(TESTER, role=Role.TESTER))
    project = make_project(projects, members, gateway, member_emails=(LEAD.email, TESTER))

    def build() -> Request:
        return Request(gateway, redis, project, members, users)

    build().screen_service.create_screen(
        LEAD, name="Đăng nhập", description="", route="", code_paths=[]
    )
    return build


def run_after_assignments_read(gateway: FakeSheetsGateway, other: Callable[[], None]) -> None:
    """Request khác chen vào ngay sau lần đọc tab Assignments tiếp theo."""

    def competing_request() -> None:
        with suppress(LockTimeout):  # bị khoá chặn lại: đúng như mong muốn
            other()

    gateway.after_next_read["Assignments"] = competing_request


def test_two_identical_assigns_create_one_row(
    gateway: FakeSheetsGateway, new_request: Callable[[], Request]
) -> None:
    run_after_assignments_read(gateway, new_request().assign_tester)

    new_request().assign_tester()

    assert len(new_request().assignments.list_all()) == 1


def test_assign_cannot_slip_in_while_removing_member(
    gateway: FakeSheetsGateway,
    members: ProjectMemberRepository,
    new_request: Callable[[], Request],
) -> None:
    run_after_assignments_read(gateway, new_request().assign_tester)

    new_request().member_service.remove_member(LEAD, TESTER)

    # Tester đã bị bỏ khỏi dự án thì không được còn việc nào trong dự án.
    assert not members.is_member("PRJ-0001", TESTER)
    assert new_request().assignments.list_all() == []


def test_assign_cannot_slip_in_while_deleting_screen(
    gateway: FakeSheetsGateway, new_request: Callable[[], Request]
) -> None:
    run_after_assignments_read(gateway, new_request().assign_tester)

    new_request().screen_service.delete_screen(LEAD, "SC-0001")

    # Màn hình đã xoá thì không được có việc nào trỏ tới nó.
    assert new_request().screens.list_all() == []
    assert new_request().assignments.list_all() == []

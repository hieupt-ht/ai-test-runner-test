"""Cache danh sách (TestCases, Assignments, Screens) trong Redis để đỡ gọi Google.

Quy tắc: ghi xong thì xoá cache; đọc TRONG khoá luôn bỏ qua cache để "kiểm tra rồi ghi"
vẫn thấy dữ liệu mới nhất.
"""

from datetime import timedelta

import fakeredis
import pytest

from app.core.models.project import Project
from app.core.models.test_case import (
    Priority,
    Severity,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.time import today_in_vietnam
from tests.conftest import make_project
from tests.fakes import FakeSheetsGateway

CONTENT = TestCaseContent(
    title="Đăng nhập",
    steps=[TestStep(action="Bấm nút", expected="")],
    expected_result="Vào được",
    severity=Severity.LOW,
    priority=Priority.P2,
)


@pytest.fixture
def project(
    gateway: FakeSheetsGateway, projects: ProjectRepository, members: ProjectMemberRepository
) -> Project:
    return make_project(projects, members, gateway)


def case_repo(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> TestCaseRepository:
    """Mỗi request dựng repository RIÊNG, nên test cũng dựng mới ở mỗi lần gọi."""
    return TestCaseRepository(
        gateway, project.spreadsheet_id, redis, project.id, cache_ttl_seconds=60
    )


def test_case_list_is_cached_across_repository_instances(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> None:
    case_repo(gateway, redis, project).create(screen_id="SC-0001", content=CONTENT, actor="a@x.com")
    case_repo(gateway, redis, project).list_all()  # lần đọc đầu: nạp cache
    gateway.calls.clear()

    cases = case_repo(gateway, redis, project).list_all()

    assert [case.id for case in cases] == ["TC-000001"]
    assert gateway.calls == []  # đọc từ Redis, không gọi Google


def test_case_write_clears_the_cache(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> None:
    repo = case_repo(gateway, redis, project)
    case = repo.create(screen_id="SC-0001", content=CONTENT, actor="a@x.com")
    assert repo.list_all()[0].status == TestCaseStatus.DRAFT  # nạp cache

    case_repo(gateway, redis, project).save(
        case.model_copy(update={"status": TestCaseStatus.IN_REVIEW}),
        expected_version=1,
        actor="a@x.com",
    )

    assert case_repo(gateway, redis, project).list_all()[0].status == TestCaseStatus.IN_REVIEW
    created = repo.create(screen_id="SC-0001", content=CONTENT, actor="a@x.com")
    assert created.id in [c.id for c in case_repo(gateway, redis, project).list_all()]


def test_get_case_is_served_from_the_cached_list(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> None:
    repo = case_repo(gateway, redis, project)
    repo.create(screen_id="SC-0001", content=CONTENT, actor="a@x.com")
    repo.list_all()
    gateway.calls.clear()

    found = case_repo(gateway, redis, project).get("TC-000001")

    assert found is not None
    assert case_repo(gateway, redis, project).get("TC-999999") is None
    assert gateway.calls == []


def test_reads_inside_the_lock_bypass_the_cache(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> None:
    repo = case_repo(gateway, redis, project)
    repo.create(screen_id="SC-0001", content=CONTENT, actor="a@x.com")
    repo.list_all()  # cache đang giữ 1 case
    # Ai đó sửa thẳng trên Sheet (không đi qua app) nên cache không biết.
    tab = gateway.data[project.spreadsheet_id]["TestCases"]
    tab.append(list(tab[1]))
    tab[-1][0] = "TC-000002"

    assert len(case_repo(gateway, redis, project).list_all()) == 1  # ngoài khoá: cache
    locked = case_repo(gateway, redis, project)
    with locked.lock():
        assert len(locked.list_all()) == 2  # trong khoá: đọc thẳng Sheet


def test_zero_ttl_means_no_cache(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> None:
    repo = TestCaseRepository(gateway, project.spreadsheet_id, redis, project.id)
    repo.create(screen_id="SC-0001", content=CONTENT, actor="a@x.com")
    repo.list_all()
    gateway.calls.clear()

    repo.list_all()

    assert gateway.calls != []


def test_assignment_list_is_cached_and_cleared_on_write(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> None:
    def repo() -> AssignmentRepository:
        return AssignmentRepository(
            gateway, project.spreadsheet_id, redis, project.id, cache_ttl_seconds=60
        )

    deadline = today_in_vietnam() + timedelta(days=7)
    created = repo().create(screen_id="SC-0001", assignee_email="a@x.com", deadline=deadline)
    repo().list_all()
    gateway.calls.clear()
    assert [a.id for a in repo().list_all()] == [created.id]
    assert gateway.calls == []

    repo().delete(created.id)

    assert repo().list_all() == []


def test_screen_list_is_cached_and_cleared_on_write(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> None:
    def repo() -> ScreenRepository:
        return ScreenRepository(
            gateway, project.spreadsheet_id, redis, project.id, cache_ttl_seconds=60
        )

    repo().create(name="Đăng nhập", description="", route="", code_paths=[])
    repo().list_all()
    gateway.calls.clear()
    assert len(repo().list_all()) == 1
    assert gateway.calls == []

    repo().create(name="Đăng ký", description="", route="", code_paths=[])

    assert len(repo().list_all()) == 2


def test_assignment_update_needs_only_four_sheet_calls(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis, project: Project
) -> None:
    repo = AssignmentRepository(gateway, project.spreadsheet_id, redis, project.id)
    deadline = today_in_vietnam() + timedelta(days=7)
    created = repo.create(screen_id="SC-0001", assignee_email="a@x.com", deadline=deadline)
    gateway.calls.clear()

    repo.update(created)

    # tiêu đề, cột id, đúng dòng, rồi ghi: không đọc lại tiêu đề và dòng thêm lần nữa
    assert len(gateway.calls) == 4

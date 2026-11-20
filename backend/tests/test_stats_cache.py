"""Cache `ProjectFacts`: đọc lần hai không chạm Sheets, ghi case/kết quả thì cache bị xoá."""

from datetime import UTC, datetime

import fakeredis
from fastapi import FastAPI

from app.api.project_facts import load_facts
from app.api.project_scope import ProjectScope, scope_for
from app.core.models.project import Project
from app.core.models.run import Result, ResultStatus
from app.core.models.test_case import (
    Priority,
    Severity,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.stats_cache import facts_cache_key
from tests.conftest import make_project
from tests.fakes import FakeSheetsGateway

CONTENT = TestCaseContent(
    title="Đăng nhập",
    steps=[TestStep(action="Mở trang", expected="")],
    expected_result="Vào được",
    severity=Severity.HIGH,
    priority=Priority.P1,
)


def fail_result(case_id: str, by: str = "lan@x.com") -> Result:
    return Result(
        id=f"RUN-1-{case_id}",
        run_id="RUN-1",
        test_case_id=case_id,
        status=ResultStatus.FAIL,
        reason="",
        failed_step=None,
        created_at=datetime(2026, 11, 19, 3, 0, tzinfo=UTC),
        executed_by=by,
        case_version=1,
    )


def setup(
    app: FastAPI,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> tuple[ProjectScope, Project]:
    project = make_project(projects, members, gateway)
    return scope_for(app.state.services, project), project


def test_second_read_does_not_touch_sheets(
    app: FastAPI,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    scope, _ = setup(app, projects, members, gateway)
    load_facts(app.state.services, scope)
    reads_after_first = len(gateway.calls)
    load_facts(app.state.services, scope)
    assert len(gateway.calls) == reads_after_first


def test_appending_result_invalidates_facts(
    app: FastAPI,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    scope, _ = setup(app, projects, members, gateway)
    assert load_facts(app.state.services, scope).results == []
    scope.results.append_batch([fail_result("TC-1")])
    assert len(load_facts(app.state.services, scope).results) == 1


def test_saving_case_invalidates_facts(
    app: FastAPI,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
) -> None:
    scope, _ = setup(app, projects, members, gateway)
    created = scope.test_cases.create(screen_id="SC-1", content=CONTENT, actor="an@x.com")
    assert load_facts(app.state.services, scope).cases[0].status == TestCaseStatus.DRAFT
    scope.test_cases.save(
        created.model_copy(update={"status": TestCaseStatus.APPROVED}),
        expected_version=created.version,
        actor="an@x.com",
    )
    assert load_facts(app.state.services, scope).cases[0].status == TestCaseStatus.APPROVED


def test_write_during_load_is_not_cached(
    app: FastAPI,
    projects: ProjectRepository,
    members: ProjectMemberRepository,
    gateway: FakeSheetsGateway,
    redis: fakeredis.FakeRedis,
) -> None:
    scope, project = setup(app, projects, members, gateway)
    # Ngay sau khi đọc xong tab Results, có người ghi kết quả mới (giả lập request khác chen vào)
    gateway.after_next_read["Results"] = lambda: scope.results.append_batch([fail_result("TC-1")])
    load_facts(app.state.services, scope)  # đọc phải thấy bản cũ, nhưng KHÔNG được lưu cache
    assert redis.get(facts_cache_key(project.id)) is None
    assert len(load_facts(app.state.services, scope).results) == 1

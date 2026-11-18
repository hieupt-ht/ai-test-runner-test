"""Thùng rác dự án: xoá vĩnh viễn dự án đã lưu trữ (repository + API)."""

import pytest

from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectNotFoundError, ProjectRepository
from tests.conftest import SHEET_A, SHEET_B, make_project
from tests.fakes import FakeSheetsGateway


def test_delete_removes_project_row(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    project = make_project(projects, members, gateway)
    projects.delete(project.id)
    assert projects.get(project.id) is None
    assert projects.list_all() == []


def test_delete_unknown_project_raises(projects: ProjectRepository) -> None:
    with pytest.raises(ProjectNotFoundError):
        projects.delete("PRJ-9999")


def test_delete_frees_spreadsheet_for_reuse(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    project = make_project(projects, members, gateway)
    projects.delete(project.id)
    assert projects.find_by_spreadsheet(SHEET_A) is None


def test_remove_all_for_project_keeps_other_projects(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    a = make_project(projects, members, gateway, member_emails=("x@x.com", "y@x.com"))
    b = make_project(
        projects, members, gateway, name="Dự án B", sheet=SHEET_B, member_emails=("x@x.com",)
    )
    assert members.remove_all_for_project(a.id) == 2
    assert members.list_for_project(a.id) == []
    assert [m.email for m in members.list_for_project(b.id)] == ["x@x.com"]


def test_remove_all_for_project_with_no_members_returns_zero(
    projects: ProjectRepository, members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    project = make_project(projects, members, gateway)
    assert members.remove_all_for_project(project.id) == 0

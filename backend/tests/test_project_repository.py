import pytest

from app.core.repositories.projects import ProjectNotFoundError, ProjectRepository
from tests.conftest import SYSTEM_SHEET_ID
from tests.fakes import FakeSheetsGateway


def create(projects: ProjectRepository, name: str, sheet: str) -> str:
    project = projects.create(
        name=name, repo_full_name="org/app", branch="main", staging_url="", spreadsheet_id=sheet
    )
    return project.id


def test_create_assigns_increasing_ids(projects: ProjectRepository) -> None:
    assert create(projects, "A", "sheet-a") == "PRJ-0001"
    assert create(projects, "B", "sheet-b") == "PRJ-0002"


def test_archived_round_trip(projects: ProjectRepository, gateway: FakeSheetsGateway) -> None:
    project_id = create(projects, "A", "sheet-a")
    project = projects.get(project_id)
    assert project is not None and project.archived is False

    projects.update(project.model_copy(update={"archived": True}))

    assert gateway.data[SYSTEM_SHEET_ID]["Projects"][1][6] == "TRUE"
    updated = projects.get(project_id)
    assert updated is not None and updated.archived is True


def test_find_by_spreadsheet(projects: ProjectRepository) -> None:
    project_id = create(projects, "A", "sheet-a")

    found = projects.find_by_spreadsheet("sheet-a")

    assert found is not None and found.id == project_id
    assert projects.find_by_spreadsheet("khac") is None


def test_update_unknown_project_raises(projects: ProjectRepository) -> None:
    project_id = create(projects, "A", "sheet-a")
    project = projects.get(project_id)
    assert project is not None

    with pytest.raises(ProjectNotFoundError):
        projects.update(project.model_copy(update={"id": "PRJ-9999"}))

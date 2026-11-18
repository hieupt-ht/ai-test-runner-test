import pytest

from app.core.repositories.projects import (
    ProjectNotFoundError,
    ProjectRepository,
    SpreadsheetInUseError,
)
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


def test_list_all_is_cached_until_next_write(
    projects: ProjectRepository, gateway: FakeSheetsGateway
) -> None:
    # Danh sách dự án được đọc ở mọi request vào dự án, nên phải cache như danh sách user.
    create(projects, "A", "sheet-a")
    gateway.calls.clear()

    projects.list_all()
    projects.get("PRJ-0001")
    projects.find_by_spreadsheet("sheet-a")

    assert gateway.calls.count("Projects") == 1

    create(projects, "B", "sheet-b")  # ghi xong thì cache bị xoá, đọc lại thấy dự án mới
    assert [p.name for p in projects.list_all()] == ["A", "B"]


def test_create_rejects_spreadsheet_already_used(projects: ProjectRepository) -> None:
    # Hai Admin bấm "Tạo" cùng lúc với cùng một Sheet: cả hai đều qua bước kiểm tra
    # ở ProjectService (lúc đó chưa ai ghi). Repository phải kiểm tra lại trong khoá.
    create(projects, "A", "sheet-a")

    with pytest.raises(SpreadsheetInUseError):
        create(projects, "B", "sheet-a")

    assert [p.name for p in projects.list_all()] == ["A"]


def test_new_project_columns_default_when_cells_empty(
    projects: ProjectRepository, gateway: FakeSheetsGateway
) -> None:
    project_id = create(projects, "A", "sheet-a")
    # Giả lập dòng cũ: ba ô mới bị Google bỏ trống ở cuối dòng
    row = gateway.data[SYSTEM_SHEET_ID]["Projects"][1]
    gateway.data[SYSTEM_SHEET_ID]["Projects"][1] = row[:8]
    projects._cache.invalidate()

    project = projects.get(project_id)

    assert project is not None
    assert project.android_app_id == "" and project.ios_bundle_id == ""
    assert project.require_review is False


def test_require_review_and_app_ids_round_trip(
    projects: ProjectRepository, gateway: FakeSheetsGateway
) -> None:
    project_id = create(projects, "A", "sheet-a")
    project = projects.get(project_id)
    assert project is not None

    projects.update(
        project.model_copy(
            update={
                "require_review": True,
                "android_app_id": "com.shop.app",
                "ios_bundle_id": "vn.shop",
            }
        )
    )

    header = gateway.data[SYSTEM_SHEET_ID]["Projects"][0]
    row = gateway.data[SYSTEM_SHEET_ID]["Projects"][1]
    assert row[header.index("require_review")] == "TRUE"
    saved = projects.get(project_id)
    assert saved is not None
    assert saved.require_review is True
    assert (saved.android_app_id, saved.ios_bundle_id) == ("com.shop.app", "vn.shop")


def test_storage_defaults_to_cloudinary_and_round_trips(
    projects: ProjectRepository, gateway: FakeSheetsGateway
) -> None:
    project_id = create(projects, "A", "sheet-a")
    project = projects.get(project_id)
    assert project is not None and project.storage == "cloudinary"

    projects.update(project.model_copy(update={"storage": "drive"}))

    header = gateway.data[SYSTEM_SHEET_ID]["Projects"][0]
    row = gateway.data[SYSTEM_SHEET_ID]["Projects"][1]
    assert row[header.index("storage")] == "drive"
    saved = projects.get(project_id)
    assert saved is not None and saved.storage == "drive"


def test_blank_storage_cell_reads_as_cloudinary(
    projects: ProjectRepository, gateway: FakeSheetsGateway
) -> None:
    # Dòng cũ chưa có cột storage (Google bỏ trống ô cuối dòng)
    project_id = create(projects, "A", "sheet-a")
    row = gateway.data[SYSTEM_SHEET_ID]["Projects"][1]
    gateway.data[SYSTEM_SHEET_ID]["Projects"][1] = row[:-1]
    projects._cache.invalidate()

    project = projects.get(project_id)

    assert project is not None and project.storage == "cloudinary"

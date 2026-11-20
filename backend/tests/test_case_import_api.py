"""Test API nhập test case từ file Excel: tải mẫu, xem trước, nhập."""

from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.core.locks.redis_lock import redis_lock
from app.core.models.project import Project
from app.core.models.screen import Screen
from app.core.models.user import Role
from app.core.repositories.projects import ProjectRepository
from app.core.repositories.users import UserRepository
from app.core.services.case_import import MAX_FILE_BYTES, parse_workbook
from app.core.services.test_cases import TestCaseService
from app.core.sheets.gateway import SheetAccessDeniedError
from app.core.sheets.table import MissingColumnsError
from tests.conftest import client_for
from tests.fakes import make_http_error
from tests.test_test_cases_api import an, lead, project, url  # noqa: F401  (fixture dùng chung)
from tests.xlsx_helpers import make_xlsx

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
BUSY_WRITE = "Google Sheets đang bận, chưa nhập case nào, hãy thử lại"


def _row(group: str = "A1", title: str = "Đăng nhập thành công") -> list[Any]:
    # Đủ 16 cột: nhóm, màn hình, yêu cầu, tiêu đề, trước, dữ liệu, điểm bắt đầu, bước, mong đợi
    # bước, kết quả, sau, mức độ, ưu tiên, nền tảng, loại test, regression
    return [group, "Đăng nhập", "", title, "", "", "", "Mở trang", "", "Vào được", "",
            "HIGH", "P1", "", "", ""]  # fmt: skip


def _files(content: bytes, name: str = "cases.xlsx") -> dict[str, Any]:
    return {"file": (name, content, XLSX)}


def test_template_roundtrips(lead: TestClient, project: Project) -> None:  # noqa: F811
    response = lead.get(url(project, "/import/template"))

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX
    assert 'filename="mau-test-case.xlsx"' in response.headers["content-disposition"]
    screens = [
        Screen(
            id="SC-0001",
            name="Đăng nhập",
            description="",
            route="/",
            code_paths=[],
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    result = parse_workbook(response.content, screens)
    assert result.errors == []
    assert len(result.cases) == 1
    assert result.cases[0].step_count == 3


def test_template_has_validation_and_guide(lead: TestClient, project: Project) -> None:  # noqa: F811
    content = lead.get(url(project, "/import/template")).content

    wb = load_workbook(BytesIO(content))
    assert "Hướng dẫn" in wb.sheetnames
    ws = wb["Test case"]
    assert ws.data_validations.dataValidation
    assert ws.freeze_panes == "A2"


def test_template_guide_warns_to_delete_example(lead: TestClient, project: Project) -> None:  # noqa: F811
    content = lead.get(url(project, "/import/template")).content

    guide = load_workbook(BytesIO(content))["Hướng dẫn"]
    lines = [str(row[0].value or "") for row in guide.iter_rows()]
    # Cảnh báo nằm ngay đầu sheet, để người mở file thấy trước khi điền
    warning_rows = [i for i, line in enumerate(lines) if "Xoá case ví dụ" in line]
    assert warning_rows and warning_rows[0] <= 3


def test_preview_writes_nothing(lead: TestClient, project: Project) -> None:  # noqa: F811
    response = lead.post(url(project, "/import/preview"), files=_files(make_xlsx([_row()])))

    assert response.status_code == 200
    assert len(response.json()["cases"]) == 1
    assert lead.get(url(project)).json() == []


def test_import_creates_and_returns_ids(lead: TestClient, project: Project) -> None:  # noqa: F811
    response = lead.post(url(project, "/import"), files=_files(make_xlsx([_row()])))

    assert response.status_code == 201
    assert response.json() == {"created": ["TC-000001"]}
    case = lead.get(url(project, "/TC-000001")).json()
    assert case["can_edit"] is True
    assert case["status"] == "DRAFT"


def test_import_with_errors_is_422_with_list(lead: TestClient, project: Project) -> None:  # noqa: F811
    bad = _row()
    bad[9] = ""  # thiếu "Kết quả mong đợi"

    response = lead.post(url(project, "/import"), files=_files(make_xlsx([bad])))

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "File còn lỗi"
    assert body["errors"][0]["column"] == "Kết quả mong đợi"
    assert lead.get(url(project)).json() == []


def test_empty_file_is_an_error(lead: TestClient, project: Project) -> None:  # noqa: F811
    empty = make_xlsx([])

    preview = lead.post(url(project, "/import/preview"), files=_files(empty))
    imported = lead.post(url(project, "/import"), files=_files(empty))

    expected = {"row": None, "column": None, "message": "File không có test case nào"}
    assert preview.status_code == 200
    assert preview.json()["errors"] == [expected]
    assert imported.status_code == 422
    assert imported.json()["errors"] == [expected]


def test_wrong_extension_and_too_big(lead: TestClient, project: Project) -> None:  # noqa: F811
    csv = lead.post(url(project, "/import/preview"), files=_files(b"a,b", "cases.csv"))
    big = lead.post(
        url(project, "/import/preview"), files=_files(b"x" * (MAX_FILE_BYTES + 1), "cases.xlsx")
    )
    csv_import = lead.post(url(project, "/import"), files=_files(b"a,b", "cases.csv"))

    assert csv.json()["errors"][0]["message"] == "Chỉ nhận file .xlsx"
    assert big.json()["errors"][0]["message"] == "File quá 2 MB"
    assert csv_import.status_code == 422
    assert csv_import.json()["errors"][0]["message"] == "Chỉ nhận file .xlsx"


def test_garbage_xlsx_is_not_500(lead: TestClient, project: Project) -> None:  # noqa: F811
    response = lead.post(url(project, "/import/preview"), files=_files(b"khong phai xlsx"))

    assert response.status_code == 200
    assert response.json()["errors"][0]["message"] == "Không đọc được file .xlsx"


def test_viewer_forbidden_and_archived_project_409(
    app: FastAPI,
    users: UserRepository,
    lead: TestClient,  # noqa: F811
    project: Project,  # noqa: F811
    projects: ProjectRepository,
) -> None:
    viewer = client_for(app, users, "viewer@x.com", Role.VIEWER)
    files = _files(make_xlsx([_row()]))
    assert viewer.post(url(project, "/import/preview"), files=files).status_code == 403
    assert viewer.get(url(project, "/import/template")).status_code == 403

    projects.update(project.model_copy(update={"archived": True}))
    admin = client_for(app, users, "admin@x.com", Role.ADMIN)
    assert admin.post(url(project, "/import"), files=files).status_code == 409


def test_lock_busy_is_409(
    lead: TestClient,  # noqa: F811
    project: Project,  # noqa: F811
    redis: fakeredis.FakeRedis,
) -> None:
    with redis_lock(redis, f"lock:{project.id}:test-cases", wait_seconds=0.1):
        response = lead.post(url(project, "/import"), files=_files(make_xlsx([_row()])))

    assert response.status_code == 409
    assert response.json() == {"detail": "Có người đang tạo case, hãy thử lại"}


@pytest.mark.parametrize(
    "error", [SheetAccessDeniedError(), MissingColumnsError(), make_http_error(500)]
)
def test_sheet_read_errors_are_503(
    lead: TestClient,  # noqa: F811
    project: Project,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(TestCaseService, "preview_import", fail)
    monkeypatch.setattr(TestCaseService, "import_cases", fail)
    files = _files(make_xlsx([_row()]))

    for path in ("/import/preview", "/import"):
        response = lead.post(url(project, path), files=files)
        assert response.status_code == 503
        assert response.json() == {"detail": BUSY_WRITE}

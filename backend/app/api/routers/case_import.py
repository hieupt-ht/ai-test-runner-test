"""Nhập test case hàng loạt từ file Excel: tải mẫu, xem trước, nhập."""

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import JSONResponse
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.routers.test_cases import service_for
from app.core.locks.redis_lock import LockTimeout
from app.core.permissions import Action
from app.core.services.case_import import (
    MAX_FILE_BYTES,
    ImportIssue,
    ParseResult,
    build_template,
)
from app.core.services.test_cases import (
    ImportModuleNotFoundError,
    ImportWriteError,
    TestCasePermissionError,
)
from app.core.sheets.gateway import SheetAccessDeniedError
from app.core.sheets.table import MissingColumnsError

# Phải đăng ký TRƯỚC router test_cases để "/import" không bị "/{case_id}" bắt mất
router = APIRouter(prefix="/api/projects/{project_id}/test-cases/import", tags=["case-import"])

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHEET_BUSY = "Google Sheets đang bận, chưa nhập case nào, hãy thử lại"
LOCK_BUSY = "Có người đang tạo case, hãy thử lại"
NO_PERMISSION = "Bạn không có quyền thực hiện thao tác này"
NO_MODULE = "Module không tồn tại"
_EMPTY_FILE = ImportIssue(row=None, message="File không có test case nào")

# Các lỗi đọc/ghi Google Sheets mà service không tự bọc: đều trả 503
_SHEET_ERRORS = (ImportWriteError, SheetAccessDeniedError, MissingColumnsError, HttpError)


class ImportCreated(BaseModel):
    created: list[str]


class ImportRejected(BaseModel):
    """Phản hồi 422: file còn lỗi, không case nào được nhập."""

    detail: str
    errors: list[ImportIssue]


def _read_upload(file: UploadFile) -> bytes:
    # Chỉ đọc tối đa MAX_FILE_BYTES + 1 byte: đủ để biết file quá lớn mà không nạp cả file khổng lồ
    return file.file.read(MAX_FILE_BYTES + 1)


def _file_problem(file: UploadFile, data: bytes) -> ImportIssue | None:
    """Lỗi chung của file (đuôi, dung lượng) cần chặn trước khi đọc nội dung."""
    if not (file.filename or "").lower().endswith(".xlsx"):
        return ImportIssue(row=None, message="Chỉ nhận file .xlsx")
    if len(data) > MAX_FILE_BYTES:
        return ImportIssue(row=None, message="File quá 2 MB")
    return None


def _rejected(errors: list[ImportIssue]) -> JSONResponse:
    """422 có `errors` nằm cùng cấp với `detail` (HTTPException không làm được điều này)."""
    body = ImportRejected(detail="File còn lỗi", errors=errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=body.model_dump(mode="json")
    )


@router.get("/template")
def download_template(project_id: str, user: CurrentUser, services: ServicesDep) -> Response:
    load_project(services, user, project_id, Action.EDIT_TEST_CASE)
    return Response(
        content=build_template(),
        media_type=XLSX_TYPE,
        headers={"Content-Disposition": 'attachment; filename="mau-test-case.xlsx"'},
    )


@router.post("/preview")
def preview_import(
    project_id: str,
    file: UploadFile,
    user: CurrentUser,
    services: ServicesDep,
    module_id: str = Form(""),
) -> ParseResult:
    project = load_project(services, user, project_id, Action.EDIT_TEST_CASE)
    data = _read_upload(file)
    problem = _file_problem(file, data)
    if problem:
        return ParseResult(errors=[problem])
    try:
        result = service_for(services, project).preview_import(
            user, data, module_id=module_id or None
        )
    except TestCasePermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_PERMISSION) from None
    except ImportModuleNotFoundError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NO_MODULE) from None
    except _SHEET_ERRORS:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, SHEET_BUSY) from None
    if not result.cases and not result.errors:
        # File trống: báo lỗi để giao diện không cho bấm Nhập
        return result.model_copy(update={"errors": [_EMPTY_FILE]})
    return result


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ImportCreated,
    responses={422: {"model": ImportRejected}},
)
def import_cases(
    project_id: str,
    file: UploadFile,
    user: CurrentUser,
    services: ServicesDep,
    module_id: str = Form(""),
) -> ImportCreated | JSONResponse:
    project = load_project(services, user, project_id, Action.EDIT_TEST_CASE)
    data = _read_upload(file)
    problem = _file_problem(file, data)
    if problem:
        return _rejected([problem])
    try:
        outcome = service_for(services, project).import_cases(
            user, data, module_id=module_id or None
        )
    except TestCasePermissionError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, NO_PERMISSION) from None
    except ImportModuleNotFoundError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NO_MODULE) from None
    except LockTimeout:
        raise HTTPException(status.HTTP_409_CONFLICT, LOCK_BUSY) from None
    except _SHEET_ERRORS:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, SHEET_BUSY) from None
    if outcome.errors:
        return _rejected(outcome.errors)
    if not outcome.created:  # file hợp lệ nhưng không có case nào: không trả 201 rỗng
        return _rejected([_EMPTY_FILE])
    return ImportCreated(created=[case.id for case in outcome.created])

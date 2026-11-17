from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, HttpUrl

from app.api.deps import CurrentUser, ServicesDep, require
from app.api.errors import github_http_error
from app.api.project_access import load_project, project_permissions
from app.api.routers.test_cases import service_for
from app.api.services import Services
from app.core.github.client import GitHubError, GitHubNotConfiguredError
from app.core.locks.redis_lock import LockTimeout
from app.core.models.project import Project
from app.core.models.user import User
from app.core.permissions import Action
from app.core.repositories.projects import SpreadsheetInUseError
from app.core.services.projects import InvalidProjectInputError, ProjectService

router = APIRouter(prefix="/api", tags=["projects"])

Name = Annotated[str, Field(min_length=1, max_length=100)]
AppId = Annotated[str, Field(max_length=200, pattern=r"^[A-Za-z0-9._-]*$")]


def _blank_to_none(value: object) -> object:
    """Ô staging URL để trống thì coi như không có."""
    return None if isinstance(value, str) and not value.strip() else value


OptionalUrl = Annotated[HttpUrl | None, BeforeValidator(_blank_to_none)]


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Name
    repo_full_name: str = Field(min_length=3)
    branch: str = Field(min_length=1)
    staging_url: OptionalUrl = None
    spreadsheet: str  # link hoặc ID của Google Sheet riêng cho dự án


class UpdateProjectRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Name | None = None
    branch: str | None = None
    staging_url: OptionalUrl = None
    archived: bool | None = None
    # Mã app mobile: chỉ chữ, số, dấu chấm, gạch dưới, gạch ngang (không có khoảng trắng)
    android_app_id: AppId | None = None
    ios_bundle_id: AppId | None = None
    require_review: bool | None = None


# Các trường mà QA Lead (thành viên dự án) cũng được đổi; trường còn lại chỉ Admin.
_SETTINGS_FIELDS = {"android_app_id", "ios_bundle_id", "require_review"}


class ProjectDetail(Project):
    permissions: list[Action]


class ServiceAccount(BaseModel):
    email: str


def _service(services: Services) -> ProjectService:
    return ProjectService(
        projects=services.projects,
        members=services.members,
        audit_log=services.audit_log,
        gateway=services.gateway,
        github=services.github,
        system_spreadsheet_id=services.system_spreadsheet_id,
        service_account_email=services.service_account_email,
    )


def _url_text(url: HttpUrl | None) -> str:
    return str(url) if url else ""


@router.get("/projects")
def list_projects(user: CurrentUser, services: ServicesDep) -> list[Project]:
    return _service(services).list_visible(user)


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(body: CreateProjectRequest, user: CurrentUser, services: ServicesDep) -> Project:
    require(user, Action.MANAGE_PROJECTS)
    try:
        return _service(services).create_project(
            user,
            name=body.name,
            repo_full_name=body.repo_full_name,
            branch=body.branch,
            staging_url=_url_text(body.staging_url),
            spreadsheet=body.spreadsheet,
        )
    except InvalidProjectInputError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except SpreadsheetInUseError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    except (GitHubNotConfiguredError, GitHubError) as error:
        raise github_http_error(error) from None
    except LockTimeout:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Hệ thống đang bận, vui lòng thử lại"
        ) from None


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: CurrentUser, services: ServicesDep) -> ProjectDetail:
    project = load_project(services, user, project_id, Action.VIEW_PROJECT)
    return ProjectDetail(
        **project.model_dump(), permissions=project_permissions(services, user, project)
    )


@router.patch("/projects/{project_id}")
def update_project(
    project_id: str, body: UpdateProjectRequest, user: CurrentUser, services: ServicesDep
) -> Project:
    only_settings = body.model_fields_set <= _SETTINGS_FIELDS
    action = Action.MANAGE_PROJECT_SETTINGS if only_settings else Action.MANAGE_PROJECTS
    project = load_project(services, user, project_id, action, allow_archived=True)
    try:
        return _service(services).update_project(
            user,
            project,
            name=body.name,
            branch=body.branch,
            # Gửi staging_url rỗng nghĩa là xoá; không gửi trường này thì giữ nguyên.
            staging_url=(
                _url_text(body.staging_url) if "staging_url" in body.model_fields_set else None
            ),
            archived=body.archived,
            android_app_id=body.android_app_id,
            ios_bundle_id=body.ios_bundle_id,
            require_review=body.require_review,
            approve_pending=lambda: _approve_pending(services, user, project),
        )
    except InvalidProjectInputError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except (GitHubNotConfiguredError, GitHubError) as error:
        raise github_http_error(error) from None
    except LockTimeout:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Hệ thống đang bận, vui lòng thử lại"
        ) from None


def _approve_pending(services: Services, user: User, project: Project) -> None:
    """Tắt bước duyệt: duyệt luôn các case đang chờ."""
    service_for(services, project).approve_all_in_review(user)


@router.get("/settings/service-account")
def service_account(user: CurrentUser, services: ServicesDep) -> ServiceAccount:
    """Email mà Admin cần share quyền Editor trên file Sheet của dự án."""
    require(user, Action.MANAGE_PROJECTS)
    return ServiceAccount(email=services.service_account_email)

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.assignment import Assignment
from app.core.models.user import User
from app.core.permissions import Action
from app.core.repositories.assignments import AssignmentNotFoundError
from app.core.services.assignments import AssignmentService, InvalidAssignmentError

router = APIRouter(prefix="/api/projects/{project_id}/assignments", tags=["assignments"])

NOT_FOUND = "Không tìm thấy việc được giao"


class AssignRequest(BaseModel):
    screen_id: str
    assignee_emails: Annotated[list[str], Field(min_length=1, max_length=20)]
    deadline: date


class ChangeDeadlineRequest(BaseModel):
    deadline: date


def _service(
    services: Services, user: User, project_id: str, action: Action
) -> AssignmentService:
    project = load_project(services, user, project_id, action)
    scope = scope_for(services, project)
    return AssignmentService(
        project_id=project.id,
        assignments=scope.assignments,
        screens=scope.screens,
        test_cases=scope.test_cases,
        members=services.members,
        users=services.users,
        audit_log=scope.audit_log,
    )


def _invalid(error: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))


def _busy() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Dữ liệu đang được cập nhật, vui lòng thử lại")


@router.get("")
def list_assignments(
    project_id: str, user: CurrentUser, services: ServicesDep, screen_id: str | None = None
) -> list[Assignment]:
    service = _service(services, user, project_id, Action.VIEW_PROJECT)
    return service.list_assignments(screen_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def assign(
    project_id: str, body: AssignRequest, user: CurrentUser, services: ServicesDep
) -> list[Assignment]:
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        return service.assign(
            user,
            screen_id=body.screen_id,
            assignee_emails=body.assignee_emails,
            deadline=body.deadline,
        )
    except InvalidAssignmentError as error:
        raise _invalid(error) from None
    except LockTimeout:
        raise _busy() from None


@router.patch("/{assignment_id}")
def change_deadline(
    project_id: str,
    assignment_id: str,
    body: ChangeDeadlineRequest,
    user: CurrentUser,
    services: ServicesDep,
) -> Assignment:
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        return service.change_deadline(user, assignment_id, body.deadline)
    except AssignmentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except InvalidAssignmentError as error:
        raise _invalid(error) from None
    except LockTimeout:
        raise _busy() from None


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign(
    project_id: str, assignment_id: str, user: CurrentUser, services: ServicesDep
) -> Response:
    service = _service(services, user, project_id, Action.MANAGE_SCREENS)
    try:
        service.unassign(user, assignment_id)
    except AssignmentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except LockTimeout:
        raise _busy() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)

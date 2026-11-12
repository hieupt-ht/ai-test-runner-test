from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.api.project_scope import scope_for
from app.api.services import Services
from app.core.locks.redis_lock import LockTimeout
from app.core.models.user import User
from app.core.permissions import Action
from app.core.repositories.members import MemberAlreadyExistsError, MemberNotFoundError
from app.core.services.members import (
    InvalidMemberError,
    MemberHasAssignmentsError,
    MemberService,
    MemberView,
)

router = APIRouter(prefix="/api/projects/{project_id}/members", tags=["members"])


class AddMemberRequest(BaseModel):
    email: str


def _service(services: Services, user: User, project_id: str, action: Action) -> MemberService:
    project = load_project(services, user, project_id, action)
    return MemberService(
        project_id=project.id,
        members=services.members,
        users=services.users,
        assignments=scope_for(services, project).assignments,
        audit_log=services.audit_log,
    )


def _busy() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "Dữ liệu đang được cập nhật, vui lòng thử lại")


@router.get("")
def list_members(project_id: str, user: CurrentUser, services: ServicesDep) -> list[MemberView]:
    return _service(services, user, project_id, Action.VIEW_PROJECT).list_members()


@router.post("", status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: str, body: AddMemberRequest, user: CurrentUser, services: ServicesDep
) -> MemberView:
    service = _service(services, user, project_id, Action.MANAGE_MEMBERS)
    try:
        return service.add_member(user, body.email)
    except InvalidMemberError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Người dùng không tồn tại hoặc đã bị khoá"
        ) from None
    except MemberAlreadyExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Người này đã là thành viên") from None
    except LockTimeout:
        raise _busy() from None


@router.delete("/{email}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    project_id: str, email: str, user: CurrentUser, services: ServicesDep
) -> Response:
    service = _service(services, user, project_id, Action.MANAGE_MEMBERS)
    try:
        service.remove_member(user, email)
    except MemberHasAssignmentsError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Người này đang được giao {error.count} màn hình, hãy bỏ giao việc trước",
        ) from None
    except MemberNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Người này không phải thành viên dự án"
        ) from None
    except LockTimeout:
        raise _busy() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)

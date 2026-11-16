"""Kiểm tra quyền khi vào một dự án.

Quy ước (xem kế hoạch M2):
- Dự án không tồn tại, hoặc user không phải thành viên (trừ Admin), hoặc dự án đã lưu trữ
  mà user không phải Admin → 404. Người ngoài không biết được dự án có tồn tại hay không.
- Là thành viên nhưng vai trò không đủ quyền → 403.
- Dự án đã lưu trữ thì chỉ được xem, ghi → 409.
"""

from fastapi import HTTPException, status

from app.api.services import Services
from app.core.models.project import Project
from app.core.models.user import Role, User
from app.core.permissions import Action, can

NOT_FOUND = "Không tìm thấy dự án"
ARCHIVED = "Dự án đã được lưu trữ"


def load_project(
    services: Services,
    user: User,
    project_id: str,
    action: Action,
    *,
    allow_archived: bool = False,
) -> Project:
    project = services.projects.get(project_id)
    is_admin = user.role == Role.ADMIN
    is_member = services.members.is_member(project_id, user.email)

    can_see = project is not None and (
        is_admin or (is_member and (not project.archived or allow_archived))
    )
    if project is None or not can_see:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)

    # Quyền theo từng test case (Tester chỉ sửa case của mình) kiểm tra sau, ở M3.
    if not can(user, action, is_member=is_member, owns_or_assigned=True):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Bạn không có quyền thực hiện thao tác này"
        )

    is_write = action != Action.VIEW_PROJECT
    if project.archived and is_write and not allow_archived:
        raise HTTPException(status.HTTP_409_CONFLICT, ARCHIVED)
    return project


def project_permissions(services: Services, user: User, project: Project) -> list[Action]:
    """Danh sách việc user được làm trong dự án, để giao diện ẩn/hiện nút."""
    is_member = services.members.is_member(project.id, user.email)
    return [
        action
        for action in Action
        if can(user, action, is_member=is_member, owns_or_assigned=True)
    ]

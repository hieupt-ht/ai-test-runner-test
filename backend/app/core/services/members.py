"""Nghiệp vụ thành viên dự án: thêm, bỏ, xem danh sách (kèm tên và vai trò)."""

from datetime import datetime

from pydantic import BaseModel

from app.core.models.user import Role, User, normalize_email
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.users import UserRepository
from app.core.services.notify import Notifier


class MemberView(BaseModel):
    email: str
    name: str
    role: Role
    active: bool
    added_at: datetime


class InvalidMemberError(Exception):
    """Email không phải người dùng đang hoạt động (trả 422)."""


class MemberHasAssignmentsError(Exception):
    def __init__(self, count: int) -> None:
        super().__init__(count)
        self.count = count


class MemberService:
    def __init__(
        self,
        *,
        project_id: str,
        members: ProjectMemberRepository,
        users: UserRepository,
        assignments: AssignmentRepository,
        audit_log: AuditLogRepository,  # nhật ký của Sheet hệ thống
        project_name: str = "",
        notifier: Notifier | None = None,
    ) -> None:
        self._project_id = project_id
        self._members = members
        self._users = users
        self._assignments = assignments
        self._audit_log = audit_log
        self._project_name = project_name
        self._notifier = notifier

    def list_members(self) -> list[MemberView]:
        views: list[MemberView] = []
        for member in self._members.list_for_project(self._project_id):
            user = self._users.get(member.email)
            views.append(
                MemberView(
                    email=member.email,
                    # User đã bị xoá khỏi tab Users vẫn hiện, để Admin dọn dẹp được
                    name=user.name if user else member.email,
                    role=user.role if user else Role.VIEWER,
                    active=user.active if user else False,
                    added_at=member.added_at,
                )
            )
        return sorted(views, key=lambda view: view.name.lower())

    def add_member(self, actor: User, email: str) -> MemberView:
        user = self._users.get(email)
        if user is None or not user.active:
            raise InvalidMemberError
        member = self._members.add(self._project_id, user.email)
        self._record(actor, "CREATE", user.email)
        if self._notifier is not None and user.email != normalize_email(actor.email):
            self._notifier.member_added(
                email=user.email, project_id=self._project_id, project_name=self._project_name
            )
        return MemberView(
            email=user.email,
            name=user.name,
            role=user.role,
            active=user.active,
            added_at=member.added_at,
        )

    def remove_member(self, actor: User, email: str) -> None:
        email = normalize_email(email)
        # Giữ khoá tab Assignments từ lúc kiểm tra tới lúc xoá xong, để không ai giao việc
        # cho người này đúng lúc họ đang bị bỏ khỏi dự án.
        with self._assignments.lock():
            assigned = [a for a in self._assignments.list_all() if a.assignee_email == email]
            if assigned:
                raise MemberHasAssignmentsError(len({a.screen_id for a in assigned}))
            self._members.remove(self._project_id, email)
        self._record(actor, "DELETE", email)

    def _record(self, actor: User, action: str, email: str) -> None:
        self._audit_log.record(
            actor=actor.email,
            action=action,
            entity="project_member",
            entity_id=f"{self._project_id}:{email}",
            diff={},
        )

"""Nghiệp vụ giao việc: giao một màn hình cho một hoặc nhiều tester, có deadline."""

from datetime import date

from app.core.models.assignment import Assignment
from app.core.models.user import Role, User, normalize_email
from app.core.repositories.assignments import AssignmentNotFoundError, AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.users import UserRepository
from app.core.time import today_in_vietnam


class InvalidAssignmentError(Exception):
    """Dữ liệu giao việc không hợp lệ (trả 422). `str(error)` là câu báo tiếng Việt."""


class AssignmentService:
    def __init__(
        self,
        *,
        project_id: str,
        assignments: AssignmentRepository,
        screens: ScreenRepository,
        members: ProjectMemberRepository,
        users: UserRepository,
        audit_log: AuditLogRepository,
    ) -> None:
        self._project_id = project_id
        self._assignments = assignments
        self._screens = screens
        self._members = members
        self._users = users
        self._audit_log = audit_log

    def list_assignments(self, screen_id: str | None = None) -> list[Assignment]:
        assignments = self._assignments.list_all()
        if screen_id is None:
            return assignments
        return [a for a in assignments if a.screen_id == screen_id]

    def assign(
        self, actor: User, *, screen_id: str, assignee_emails: list[str], deadline: date
    ) -> list[Assignment]:
        """Tạo việc cho các tester chưa được giao màn hình này; cặp đã có thì bỏ qua."""
        if self._screens.get(screen_id) is None:
            raise InvalidAssignmentError("Không tìm thấy màn hình")
        _check_deadline(deadline)

        emails = list(dict.fromkeys(normalize_email(email) for email in assignee_emails))
        for email in emails:
            self._check_assignee(email)

        already = {a.assignee_email for a in self.list_assignments(screen_id)}
        created: list[Assignment] = []
        for email in emails:
            if email in already:
                continue
            assignment = self._assignments.create(
                screen_id=screen_id, assignee_email=email, deadline=deadline
            )
            self._record(actor, "CREATE", assignment)
            created.append(assignment)
        return created

    def change_deadline(self, actor: User, assignment_id: str, deadline: date) -> Assignment:
        current = self._assignments.get(assignment_id)
        if current is None:
            raise AssignmentNotFoundError(assignment_id)
        _check_deadline(deadline)
        updated = self._assignments.update(current.model_copy(update={"deadline": deadline}))
        self._audit_log.record(
            actor=actor.email,
            action="UPDATE",
            entity="assignment",
            entity_id=assignment_id,
            diff={"deadline": [current.deadline.isoformat(), deadline.isoformat()]},
        )
        return updated

    def unassign(self, actor: User, assignment_id: str) -> None:
        current = self._assignments.get(assignment_id)
        if current is None:
            raise AssignmentNotFoundError(assignment_id)
        self._assignments.delete(assignment_id)
        self._record(actor, "DELETE", current)

    def _check_assignee(self, email: str) -> None:
        user = self._users.get(email)
        is_active_tester = user is not None and user.active and user.role == Role.TESTER
        if not (is_active_tester and self._members.is_member(self._project_id, email)):
            raise InvalidAssignmentError(f"{email} không phải tester đang hoạt động của dự án")

    def _record(self, actor: User, action: str, assignment: Assignment) -> None:
        self._audit_log.record(
            actor=actor.email,
            action=action,
            entity="assignment",
            entity_id=assignment.id,
            diff=assignment.model_dump(mode="json"),
        )


def _check_deadline(deadline: date) -> None:
    if deadline < today_in_vietnam():
        raise InvalidAssignmentError("Deadline phải từ hôm nay trở đi")

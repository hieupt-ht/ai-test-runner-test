"""Nghiệp vụ nhận việc theo module.

Việc giao theo màn hình (`Assignments`) vẫn là thứ quyết định quyền và kết quả. Service này
chỉ giữ cho nó khớp với `ModuleAssignments`: nhận module thì có việc cho mọi màn hình của module,
bỏ nhận thì mất các việc đó (case đã viết vẫn còn nguyên).

Thứ tự khoá luôn là: screens → assignments → module-assignments.
Backend KHÔNG chặn khi module đã có người làm; cảnh báo chỉ là việc của giao diện.
"""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import date, timedelta

from app.core.assignment_status import derive_assignment_status
from app.core.models.assignment import Assignment
from app.core.models.module import ModuleAssignment
from app.core.models.user import Role, User, normalize_email
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository, AuditRecord
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.modules import (
    ModuleAssignmentNotFoundError,
    ModuleAssignmentRepository,
    ModuleNotFoundError,
    ModuleRepository,
)
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.repositories.users import UserRepository
from app.core.services.assignments import (
    InvalidAssignmentError,
    check_deadline,
    is_active_tester_member,
)
from app.core.services.notify import Notifier
from app.core.time import today_in_vietnam

_LEAD_ROLES = {Role.ADMIN, Role.QA_LEAD}


class ModuleWorkPermissionError(Exception):
    """Tester chỉ được tự nhận / bỏ nhận / đổi hạn việc của chính mình (trả 403)."""


class ModuleWorkService:
    def __init__(
        self,
        *,
        project_id: str,
        modules: ModuleRepository,
        screens: ScreenRepository,
        assignments: AssignmentRepository,
        module_assignments: ModuleAssignmentRepository,
        test_cases: TestCaseRepository,
        members: ProjectMemberRepository,
        users: UserRepository,
        audit_log: AuditLogRepository,
        notifier: Notifier | None = None,
    ) -> None:
        self._project_id = project_id
        self._modules = modules
        self._screens = screens
        self._assignments = assignments
        self._module_assignments = module_assignments
        self._test_cases = test_cases
        self._members = members
        self._users = users
        self._audit_log = audit_log
        self._notifier = notifier

    def assign(
        self, actor: User, *, module_id: str, emails: list[str], deadline: date
    ) -> list[ModuleAssignment]:
        """Giao module (QA: cho ai cũng được; tester: chỉ tự nhận). Trả các dòng mới tạo."""
        check_deadline(deadline)
        wanted = list(dict.fromkeys(normalize_email(email) for email in emails))
        if not _is_lead(actor) and wanted != [normalize_email(actor.email)]:
            raise ModuleWorkPermissionError("Tester chỉ được tự nhận module cho chính mình")

        with self._locks():
            module = self._modules.get(module_id)
            if module is None:
                raise ModuleNotFoundError(module_id)
            for email in wanted:
                if not is_active_tester_member(self._users, self._members, self._project_id, email):
                    raise InvalidAssignmentError(
                        f"{email} không phải tester đang hoạt động của dự án"
                    )
            rows = {
                w.assignee_email: w
                for w in self._module_assignments.list_all()
                if w.module_id == module_id
            }
            created = self._module_assignments.create_many(
                [(module_id, email, deadline) for email in wanted if email not in rows]
            )
            rows.update({w.assignee_email: w for w in created})
            screen_ids = [s.id for s in self._screens.list_all() if s.module_id == module_id]
            self._create_screen_assignments(
                screen_ids, [(email, rows[email].deadline) for email in wanted]
            )

        self._record_many(actor, "CREATE", created)
        if self._notifier is not None:
            for row in created:
                if row.assignee_email != normalize_email(actor.email):
                    self._notifier.module_assigned(
                        email=row.assignee_email,
                        project_id=self._project_id,
                        module_id=module_id,
                        module_name=module.name,
                    )
        return created

    def unassign(
        self, actor: User, module_assignment_id: str, *, module_id: str | None = None
    ) -> int:
        """Bỏ nhận module: xoá dòng nhận và mọi việc giao màn hình của người đó trong module."""
        with self._locks():
            row = self._find_row(module_assignment_id, module_id)
            _check_may_touch(actor, row)
            screen_ids = self._module_screen_ids(row.module_id)
            mine = [
                a.id
                for a in self._assignments.list_all()
                if a.assignee_email == row.assignee_email and a.screen_id in screen_ids
            ]
            self._assignments.delete_many(mine)
            self._module_assignments.delete_many([row.id])
        self._record_many(actor, "DELETE", [row])
        return len(mine)

    def change_deadline(
        self,
        actor: User,
        module_assignment_id: str,
        deadline: date,
        *,
        module_id: str | None = None,
    ) -> ModuleAssignment:
        check_deadline(deadline)
        with self._locks():
            row = self._find_row(module_assignment_id, module_id)
            _check_may_touch(actor, row)
            screen_ids = self._module_screen_ids(row.module_id)
            updated = row.model_copy(update={"deadline": deadline})
            self._module_assignments.update_many([updated])
            self._assignments.update_many(
                [
                    a.model_copy(update={"deadline": deadline})
                    for a in self._assignments.list_all()
                    if a.assignee_email == row.assignee_email and a.screen_id in screen_ids
                ]
            )
        self._audit_log.record(
            actor=actor.email,
            action="UPDATE",
            entity="module_assignment",
            entity_id=row.id,
            diff={"deadline": [row.deadline.isoformat(), deadline.isoformat()]},
        )
        return updated

    def assign_new_screens(
        self, screen_ids: list[str], module_id: str, *, also: str | None = None
    ) -> list[Assignment]:
        """Giao các màn hình mới của module cho mọi người đang làm module đó.

        Bỏ qua người không còn là tester đang hoạt động + thành viên dự án. `also` là người
        đang nhập file: luôn được giao, hạn lấy từ dòng nhận module của họ.
        """
        also_email = normalize_email(also) if also else None
        with self._locks():
            people = [
                (w.assignee_email, w.deadline)
                for w in self._module_assignments.list_all()
                if w.module_id == module_id
                and (
                    w.assignee_email == also_email
                    or is_active_tester_member(
                        self._users, self._members, self._project_id, w.assignee_email
                    )
                )
            ]
            return self._create_screen_assignments(screen_ids, people)

    def default_deadline(self, module_id: str) -> date:
        """Hạn xa nhất trong module; module chưa có ai làm thì lấy hôm nay + 7 ngày."""
        rows = self._module_assignments.list_all()
        deadlines = [w.deadline for w in rows if w.module_id == module_id]
        return max(deadlines, default=today_in_vietnam() + timedelta(days=7))

    # ----- nội bộ -----

    @contextmanager
    def _locks(self) -> Iterator[None]:
        """Giữ ba khoá theo đúng thứ tự screens → assignments → module-assignments."""
        with ExitStack() as stack:
            stack.enter_context(self._screens.lock())
            stack.enter_context(self._assignments.lock())
            stack.enter_context(self._module_assignments.lock())
            yield

    def _find_row(self, module_assignment_id: str, module_id: str | None) -> ModuleAssignment:
        row = next(
            (w for w in self._module_assignments.list_all() if w.id == module_assignment_id), None
        )
        if row is None or (module_id is not None and row.module_id != module_id):
            raise ModuleAssignmentNotFoundError(module_assignment_id)
        return row

    def _module_screen_ids(self, module_id: str) -> set[str]:
        return {s.id for s in self._screens.list_all() if s.module_id == module_id}

    def _create_screen_assignments(
        self, screen_ids: list[str], people: list[tuple[str, date]]
    ) -> list[Assignment]:
        """Giao từng màn hình cho từng người (cặp đã có thì bỏ qua), ghi một lượt."""
        if not screen_ids or not people:
            return []
        existing = {(a.screen_id, a.assignee_email) for a in self._assignments.list_all()}
        # Tester có thể đã viết case trên màn hình này từ trước, nên trạng thái ban đầu
        # tính từ case hiện có chứ không mặc định TODO.
        cases = self._test_cases.list_all()
        items = [
            (
                screen_id,
                email,
                deadline,
                derive_assignment_status(cases, screen_id=screen_id, tester_email=email),
            )
            for screen_id in screen_ids
            for email, deadline in people
            if (screen_id, email) not in existing
        ]
        return self._assignments.create_many(items)

    def _record_many(self, actor: User, action: str, rows: list[ModuleAssignment]) -> None:
        if not rows:
            return
        self._audit_log.record_many(
            [
                AuditRecord(
                    actor=actor.email,
                    action=action,
                    entity="module_assignment",
                    entity_id=row.id,
                    diff=row.model_dump(mode="json"),
                )
                for row in rows
            ]
        )


def _is_lead(user: User) -> bool:
    return user.role in _LEAD_ROLES


def _check_may_touch(actor: User, row: ModuleAssignment) -> None:
    if not _is_lead(actor) and row.assignee_email != normalize_email(actor.email):
        raise ModuleWorkPermissionError("Bạn chỉ được thao tác trên việc của chính mình")

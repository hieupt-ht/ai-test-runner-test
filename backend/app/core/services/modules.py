"""Nghiệp vụ module: tạo, sửa, xoá, xem kèm số màn hình và người đang làm."""

from datetime import date
from typing import Any

from pydantic import BaseModel

from app.core.models.module import Module, name_key
from app.core.models.user import User
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.modules import (
    ModuleAssignmentRepository,
    ModuleNotFoundError,
    ModuleRepository,
)
from app.core.repositories.screens import ScreenRepository
from app.core.repositories.users import UserRepository


class DuplicateModuleNameError(ValueError):
    """Đã có module cùng tên (trả 422)."""


class ModuleHasScreensError(Exception):
    """Module còn màn hình nên chưa xoá được (trả 409)."""


class ModuleWorker(BaseModel):
    assignment_id: str
    email: str
    name: str
    deadline: date


class ModuleView(Module):
    screen_count: int
    workers: list[ModuleWorker]


class ModuleService:
    def __init__(
        self,
        modules: ModuleRepository,
        screens: ScreenRepository,
        module_assignments: ModuleAssignmentRepository,
        users: UserRepository,
        audit_log: AuditLogRepository,
    ) -> None:
        self._modules = modules
        self._screens = screens
        self._module_assignments = module_assignments
        self._users = users
        self._audit_log = audit_log

    def list_modules(self) -> list[ModuleView]:
        screens = self._screens.list_all()
        workers = self._module_assignments.list_all()
        names = {user.email: user.name for user in self._users.list_all()}
        return [
            ModuleView(
                **module.model_dump(),
                screen_count=sum(1 for s in screens if s.module_id == module.id),
                workers=[
                    ModuleWorker(
                        assignment_id=w.id,
                        email=w.assignee_email,
                        name=names.get(w.assignee_email, w.assignee_email),
                        deadline=w.deadline,
                    )
                    for w in workers
                    if w.module_id == module.id
                ],
            )
            for module in self._modules.list_all()
        ]

    def create_module(self, actor: User, *, name: str, description: str) -> Module:
        with self._modules.lock():
            self._check_name_free(name)
            module = self._modules.create(name=name, description=description)
        self._record(actor, "CREATE", module.id, module.model_dump(mode="json"))
        return module

    def update_module(
        self, actor: User, module_id: str, *, name: str | None, description: str | None
    ) -> Module:
        with self._modules.lock():
            current = self._modules.get(module_id)
            if current is None:
                raise ModuleNotFoundError(module_id)
            if name is not None and name_key(name) != name_key(current.name):
                self._check_name_free(name)
            changes = {"name": name, "description": description}
            updated = current.model_copy(
                update={field: value for field, value in changes.items() if value is not None}
            )
            old, new = current.model_dump(mode="json"), updated.model_dump(mode="json")
            diff = {field: [old[field], new[field]] for field in old if old[field] != new[field]}
            if not diff:
                return current
            self._modules.update(updated)
        self._record(actor, "UPDATE", module_id, diff)
        return updated

    def delete_module(self, actor: User, module_id: str) -> None:
        # Khoá screens trước (không ai thêm màn hình vào module lúc đang xoá), rồi tới việc module
        with self._screens.lock(), self._module_assignments.lock():
            if self._modules.get(module_id) is None:
                raise ModuleNotFoundError(module_id)
            if any(s.module_id == module_id for s in self._screens.list_all()):
                raise ModuleHasScreensError(module_id)
            self._module_assignments.delete_many(
                [w.id for w in self._module_assignments.list_all() if w.module_id == module_id]
            )
            self._modules.delete(module_id)
        self._record(actor, "DELETE", module_id, {})

    def _check_name_free(self, name: str) -> None:
        if any(name_key(m.name) == name_key(name) for m in self._modules.list_all()):
            raise DuplicateModuleNameError("Đã có module tên này")

    def _record(self, actor: User, action: str, module_id: str, diff: dict[str, Any]) -> None:
        self._audit_log.record(
            actor=actor.email, action=action, entity="module", entity_id=module_id, diff=diff
        )

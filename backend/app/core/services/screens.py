"""Nghiệp vụ màn hình: tạo, sửa, xoá, kèm ghi nhật ký vào Sheet dự án."""

from typing import Any

from app.core.models.screen import Screen
from app.core.models.user import User
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.screens import ScreenNotFoundError, ScreenRepository


class ScreenService:
    def __init__(self, screens: ScreenRepository, audit_log: AuditLogRepository) -> None:
        self._screens = screens
        self._audit_log = audit_log

    def list_screens(self) -> list[Screen]:
        return self._screens.list_all()

    def create_screen(
        self, actor: User, *, name: str, description: str, route: str, code_paths: list[str]
    ) -> Screen:
        screen = self._screens.create(
            name=name, description=description, route=route, code_paths=code_paths
        )
        self._record(actor, "CREATE", screen.id, screen.model_dump(mode="json"))
        return screen

    def update_screen(
        self,
        actor: User,
        screen_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        route: str | None = None,
        code_paths: list[str] | None = None,
    ) -> Screen:
        current = self._screens.get(screen_id)
        if current is None:
            raise ScreenNotFoundError(screen_id)
        changes = {
            "name": name,
            "description": description,
            "route": route,
            "code_paths": code_paths,
        }
        updated = current.model_copy(
            update={field: value for field, value in changes.items() if value is not None}
        )
        old, new = current.model_dump(mode="json"), updated.model_dump(mode="json")
        diff = {field: [old[field], new[field]] for field in old if old[field] != new[field]}
        if not diff:
            return current
        self._screens.update(updated)
        self._record(actor, "UPDATE", screen_id, diff)
        return updated

    def delete_screen(self, actor: User, screen_id: str) -> None:
        self._screens.delete(screen_id)
        self._record(actor, "DELETE", screen_id, {})

    def _record(self, actor: User, action: str, screen_id: str, diff: dict[str, Any]) -> None:
        self._audit_log.record(
            actor=actor.email, action=action, entity="screen", entity_id=screen_id, diff=diff
        )

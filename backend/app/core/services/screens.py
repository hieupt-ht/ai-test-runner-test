"""Nghiệp vụ màn hình: tạo, sửa, xoá, kèm ghi nhật ký vào Sheet dự án."""

from collections.abc import Callable
from typing import Any

from app.core.models.media import ForeignMediaError, Media, ensure_own_media
from app.core.models.module import name_key
from app.core.models.screen import Screen
from app.core.models.user import User
from app.core.repositories.assignments import AssignmentRepository
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.modules import ModuleRepository
from app.core.repositories.screens import ScreenNotFoundError, ScreenRepository
from app.core.repositories.test_cases import TestCaseRepository
from app.core.services.evidence_retention import MediaDeleter


class ScreenInUseError(Exception):
    """Màn hình đang được giao cho tester nên chưa xoá được."""


class ScreenHasTestCasesError(Exception):
    """Màn hình đang có test case (kể cả case đã DEPRECATED) nên không xoá được."""


class InvalidScreenError(ValueError):
    """Dữ liệu màn hình không hợp lệ (ví dụ ảnh không thuộc kho lưu trữ của app)."""


class DuplicateScreenNameError(InvalidScreenError):
    """Module đã có màn hình cùng tên (trả 422)."""


class ScreenService:
    def __init__(
        self,
        screens: ScreenRepository,
        assignments: AssignmentRepository,
        test_cases: TestCaseRepository,
        audit_log: AuditLogRepository,
        *,
        modules: ModuleRepository,
        on_screens_added: Callable[[list[str], str], None] | None = None,
        cloud_name: str = "",
        drive_enabled: bool = False,
        janitor: MediaDeleter | None = None,
    ) -> None:
        self._screens = screens
        self._assignments = assignments
        self._test_cases = test_cases
        self._audit_log = audit_log
        self._modules = modules
        # Gọi sau khi màn hình được tạo/chuyển vào module: (mã màn hình, mã module)
        self._on_screens_added = on_screens_added
        self._cloud_name = cloud_name
        self._drive_enabled = drive_enabled
        self._janitor = janitor

    def list_screens(self) -> list[Screen]:
        return self._screens.list_all()

    def create_screen(
        self,
        actor: User,
        *,
        name: str,
        description: str,
        route: str,
        code_paths: list[str],
        dev_owner: str = "",
        media: list[Media] | None = None,
        module_id: str = "",
    ) -> Screen:
        self._require_own_media(media or [])
        with self._screens.lock():  # kiểm tra tên trùng rồi tạo, không ai chen vào giữa
            self._check_module(module_id, name, exclude_id=None)
            screen = self._screens.create(
                name=name,
                description=description,
                route=route,
                code_paths=code_paths,
                dev_owner=dev_owner,
                media=media,
                module_id=module_id,
            )
            try:
                self._notify_added([screen.id], module_id)
            except Exception:
                # Giao việc lỗi thì gỡ màn hình vừa tạo, để không còn màn hình mồ côi
                self._screens.delete(screen.id)
                raise
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
        dev_owner: str | None = None,
        media: list[Media] | None = None,
        module_id: str | None = None,
    ) -> Screen:
        if media is not None:
            self._require_own_media(media)
        with self._screens.lock():
            current = self._screens.get(screen_id)
            if current is None:
                raise ScreenNotFoundError(screen_id)
            changes = {
                "name": name,
                "description": description,
                "route": route,
                "code_paths": code_paths,
                "dev_owner": dev_owner,
                "media": media,
                "module_id": module_id,
            }
            updated = current.model_copy(
                update={field: value for field, value in changes.items() if value is not None}
            )
            old, new = current.model_dump(mode="json"), updated.model_dump(mode="json")
            diff = {field: [old[field], new[field]] for field in old if old[field] != new[field]}
            if not diff:
                return current
            if "name" in diff or "module_id" in diff:
                self._check_module(updated.module_id, updated.name, exclude_id=screen_id)
            self._screens.update(updated)
            if "module_id" in diff:
                self._notify_added([screen_id], updated.module_id)
        self._clean_removed_media(current, updated)
        self._record(actor, "UPDATE", screen_id, diff)
        return updated

    def delete_screen(self, actor: User, screen_id: str) -> None:
        # Giữ khoá tab Assignments từ lúc kiểm tra tới lúc xoá xong, để không ai giao
        # màn hình này cho tester đúng lúc nó đang bị xoá.
        # Khoá tab TestCases lồng bên trong (luôn assignments trước, test-cases sau) để
        # không ai tạo test case mới trên màn hình đúng lúc nó đang bị xoá.
        # Thứ tự khoá: screens → assignments → test-cases.
        with self._screens.lock(), self._assignments.lock(), self._test_cases.lock():
            screen = self._screens.get(screen_id)
            if any(case.screen_id == screen_id for case in self._test_cases.list_all()):
                raise ScreenHasTestCasesError(screen_id)
            mine = [a.id for a in self._assignments.list_all() if a.screen_id == screen_id]
            if mine and (screen is None or not screen.module_id):
                raise ScreenInUseError(screen_id)
            # Màn hình thuộc module: việc giao do module tự sinh, nên xoá kèm cho gọn
            self._assignments.delete_many(mine)
            self._screens.delete(screen_id)
        # Xoá hẳn màn hình thì ảnh/video của nó cũng không còn chỗ dùng
        if screen is not None and self._janitor is not None:
            self._janitor.delete(screen.media)
        self._record(actor, "DELETE", screen_id, {})

    def _check_module(self, module_id: str, name: str, *, exclude_id: str | None) -> None:
        """Module phải có thật và chưa có màn hình trùng tên (không thuộc module thì bỏ qua)."""
        if not module_id:
            return
        if self._modules.get(module_id) is None:
            raise InvalidScreenError("Module không tồn tại")
        key = name_key(name)
        for other in self._screens.list_all():
            if (
                other.module_id == module_id
                and other.id != exclude_id
                and name_key(other.name) == key
            ):
                raise DuplicateScreenNameError("Module đã có màn hình tên này")

    def _notify_added(self, screen_ids: list[str], module_id: str) -> None:
        if module_id and self._on_screens_added is not None:
            self._on_screens_added(screen_ids, module_id)

    def _require_own_media(self, media: list[Media]) -> None:
        """Mọi ảnh/video phải nằm trong kho của app (Cloudinary/Drive), không thì không ghi gì."""
        try:
            ensure_own_media(media, self._cloud_name, self._drive_enabled)
        except ForeignMediaError as error:
            raise InvalidScreenError(str(error)) from None

    def _clean_removed_media(self, old: Screen, new: Screen) -> None:
        """Xoá file của ảnh bản cũ có mà bản mới không còn (so theo public_id)."""
        if self._janitor is None:
            return
        kept = {item.public_id for item in new.media}
        removed = [item for item in old.media if item.public_id not in kept]
        if removed:
            self._janitor.delete(removed)

    def _record(self, actor: User, action: str, screen_id: str, diff: dict[str, Any]) -> None:
        self._audit_log.record(
            actor=actor.email, action=action, entity="screen", entity_id=screen_id, diff=diff
        )

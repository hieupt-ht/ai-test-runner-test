"""Nghiệp vụ quản lý user: tạo, sửa, ghi nhật ký.

Router chỉ kiểm tra quyền rồi gọi vào đây.
"""

from typing import Any

from app.core.models.user import Role, User, normalize_email
from app.core.passwords import hash_password
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.users import UserNotFoundError, UserRepository
from app.core.time import utc_now


class CannotChangeSelfError(Exception):
    """Admin tự khoá hoặc tự hạ quyền mình: chặn lại để hệ thống không mất Admin."""


def _diff(before: User, after: User) -> dict[str, list[Any]]:
    """Chỉ giữ các trường bị đổi, dạng {tên_trường: [giá_trị_cũ, giá_trị_mới]}."""
    old, new = before.model_dump(mode="json"), after.model_dump(mode="json")
    return {field: [old[field], new[field]] for field in old if old[field] != new[field]}


class UserService:
    def __init__(self, users: UserRepository, audit_log: AuditLogRepository) -> None:
        self._users = users
        self._audit_log = audit_log

    def list_users(self) -> list[User]:
        return self._users.list_all()

    def create_user(self, actor: User, *, email: str, name: str, role: Role, password: str) -> User:
        user = self._users.create(
            User(email=email, name=name, role=role, active=True, created_at=utc_now()),
            password_hash=hash_password(password),
        )
        self._audit_log.record(
            actor=actor.email,
            action="CREATE",
            entity="user",
            entity_id=user.email,
            diff=user.model_dump(mode="json"),
        )
        return user

    def reset_password(self, actor: User, email: str, password: str) -> None:
        """Admin đặt mật khẩu mới cho một user. Nhật ký không ghi mật khẩu hay hash."""
        target = self._users.get(email)
        if target is None:
            raise UserNotFoundError(normalize_email(email))
        self._users.set_password_hash(target.email, hash_password(password))
        self._audit_log.record(
            actor=actor.email,
            action="RESET_PASSWORD",
            entity="user",
            entity_id=target.email,
            diff={},
        )

    def update_user(
        self,
        actor: User,
        email: str,
        *,
        name: str | None = None,
        role: Role | None = None,
        active: bool | None = None,
    ) -> User:
        current = self._users.get(email)
        if current is None:
            raise UserNotFoundError(normalize_email(email))

        is_self = current.email == actor.email
        if is_self and (active is False or (role is not None and role != Role.ADMIN)):
            raise CannotChangeSelfError

        changes = {"name": name, "role": role, "active": active}
        updated = current.model_copy(
            update={field: value for field, value in changes.items() if value is not None}
        )
        diff = _diff(current, updated)
        if not diff:
            return current  # không có gì thay đổi thì không ghi

        self._users.update(updated)
        self._audit_log.record(
            actor=actor.email, action="UPDATE", entity="user", entity_id=updated.email, diff=diff
        )
        return updated

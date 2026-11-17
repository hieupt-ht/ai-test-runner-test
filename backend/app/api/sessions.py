"""Lưu phiên đăng nhập trong Redis. Trình duyệt chỉ giữ mã phiên trong cookie httpOnly."""

import secrets

from redis import Redis

from app.core.models.user import normalize_email

SESSION_COOKIE = "atr_session"


class SessionStore:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def create(self, email: str) -> str:
        session_id = secrets.token_urlsafe(32)
        self._redis.set(self._key(session_id), email, ex=self._ttl_seconds)
        # Ghi nhớ các phiên của từng người để xoá hết một lượt khi đổi/đặt lại mật khẩu.
        user_key = self._user_key(email)
        self._redis.sadd(user_key, session_id)
        self._redis.expire(user_key, self._ttl_seconds)
        return session_id

    def get_email(self, session_id: str) -> str | None:
        """Trả về email của phiên; mỗi lần dùng thì gia hạn thêm (phiên "trượt")."""
        key = self._key(session_id)
        email = self._redis.get(key)
        if email is None:
            return None
        self._redis.expire(key, self._ttl_seconds)
        # Danh sách phiên của user phải sống ít nhất bằng phiên, để đổi mật khẩu xoá được hết.
        self._redis.expire(
            self._user_key(email.decode() if isinstance(email, bytes) else str(email)),
            self._ttl_seconds,
        )
        return email.decode() if isinstance(email, bytes) else str(email)

    def delete(self, session_id: str) -> None:
        self._redis.delete(self._key(session_id))

    def delete_all_for(self, email: str) -> None:
        """Xoá mọi phiên của email này (đăng xuất khỏi mọi trình duyệt)."""
        user_key = self._user_key(email)
        for raw in self._redis.smembers(user_key):
            session_id = raw.decode() if isinstance(raw, bytes) else str(raw)
            self._redis.delete(self._key(session_id))
        self._redis.delete(user_key)

    @staticmethod
    def _user_key(email: str) -> str:
        return f"user_sessions:{normalize_email(email)}"

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"

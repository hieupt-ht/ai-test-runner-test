"""Lưu phiên đăng nhập trong Redis. Trình duyệt chỉ giữ mã phiên trong cookie httpOnly."""

import secrets

from redis import Redis

SESSION_COOKIE = "atr_session"


class SessionStore:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def create(self, email: str) -> str:
        session_id = secrets.token_urlsafe(32)
        self._redis.set(self._key(session_id), email, ex=self._ttl_seconds)
        return session_id

    def get_email(self, session_id: str) -> str | None:
        """Trả về email của phiên; mỗi lần dùng thì gia hạn thêm (phiên "trượt")."""
        key = self._key(session_id)
        email = self._redis.get(key)
        if email is None:
            return None
        self._redis.expire(key, self._ttl_seconds)
        return email.decode() if isinstance(email, bytes) else str(email)

    def delete(self, session_id: str) -> None:
        self._redis.delete(self._key(session_id))

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"

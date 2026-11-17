"""Chống dò mật khẩu: đếm số lần đăng nhập sai theo email trong Redis.

Sai MAX_FAILED_LOGINS lần thì khoá LOCK_SECONDS giây. Email không tồn tại cũng bị đếm
như email thật, để kẻ dò không biết email nào có trong hệ thống.
"""

from redis import Redis

from app.core.models.user import normalize_email

MAX_FAILED_LOGINS = 5
LOCK_SECONDS = 15 * 60


class LoginThrottle:
    def __init__(
        self,
        redis: Redis,
        *,
        max_failures: int = MAX_FAILED_LOGINS,
        lock_seconds: int = LOCK_SECONDS,
    ) -> None:
        self._redis = redis
        self._max_failures = max_failures
        self._lock_seconds = lock_seconds

    def is_locked(self, email: str) -> bool:
        count = self._redis.get(self._key(email))
        return count is not None and int(count) >= self._max_failures

    def record_failure(self, email: str) -> None:
        key = self._key(email)
        count = self._redis.incr(key)
        if count == 1 or count == self._max_failures:
            # Lần đầu: bắt đầu đếm giờ. Lần chạm ngưỡng: tính lại 15 phút khoá từ lúc này.
            self._redis.expire(key, self._lock_seconds)

    def reset(self, email: str) -> None:
        self._redis.delete(self._key(email))

    @staticmethod
    def _key(email: str) -> str:
        return f"login_fail:{normalize_email(email)}"

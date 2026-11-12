"""Khoá dùng Redis: đảm bảo tại một thời điểm chỉ một request được sửa một bản ghi.

Quy ước tên khoá (xem spec mục 9):
- dữ liệu trong dự án: `lock:<project_id>:<entity>:<id>`
- dữ liệu hệ thống:    `lock:system:<entity>:<id>`
"""

import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager

from redis import Redis

# Chỉ xoá khoá nếu nó vẫn là của mình (giá trị bằng token mình đã đặt).
# Phải làm trong một script Lua để "kiểm tra rồi xoá" không bị ai chen vào giữa.
_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class LockTimeout(Exception):
    """Chờ quá lâu mà không lấy được khoá (có người khác đang giữ)."""


@contextmanager
def redis_lock(
    redis: Redis,
    key: str,
    *,
    ttl_seconds: int = 10,
    wait_seconds: float = 5.0,
    poll_seconds: float = 0.05,
) -> Iterator[None]:
    token = secrets.token_hex(16)
    deadline = time.monotonic() + wait_seconds

    # SET ... NX PX: chỉ đặt được khi khoá chưa tồn tại, và tự hết hạn sau ttl
    # (để khoá không bị kẹt mãi nếu tiến trình chết giữa chừng).
    while not redis.set(key, token, nx=True, px=ttl_seconds * 1000):
        if time.monotonic() >= deadline:
            raise LockTimeout(f"Không lấy được khoá {key}")
        time.sleep(poll_seconds)

    try:
        yield
    finally:
        redis.eval(_RELEASE_SCRIPT, 1, key, token)

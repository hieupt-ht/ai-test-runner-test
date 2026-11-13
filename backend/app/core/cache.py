"""Cache trong Redis có "bộ đếm thế hệ".

Vấn đề: request A đọc Sheet (mất vài trăm ms); trong lúc đó request B ghi dữ liệu mới và xoá
cache; A đọc xong lại ghi dữ liệu CŨ vào cache. Bộ đếm thế hệ chặn việc này: A nhớ thế hệ
trước khi đọc, và chỉ được ghi cache nếu thế hệ chưa đổi.
"""

import json
from collections.abc import Callable

from pydantic import BaseModel
from redis import Redis

# "Kiểm tra thế hệ rồi ghi" làm trong một script Lua để không ai chen vào giữa.
_SET_IF_GENERATION_UNCHANGED = """
local current = redis.call('get', KEYS[2]) or ''
if current == ARGV[1] then
    redis.call('set', KEYS[1], ARGV[2], 'EX', ARGV[3])
    return 1
end
return 0
"""


class GenerationCache:
    def __init__(self, redis: Redis, key: str, ttl_seconds: int) -> None:
        self._redis = redis
        self._key = key
        self._generation_key = f"{key}:generation"
        self._ttl_seconds = ttl_seconds

    def get(self) -> str | None:
        value = self._redis.get(self._key)
        return _to_text(value)

    def generation(self) -> str:
        return _to_text(self._redis.get(self._generation_key)) or ""

    def set_if_unchanged(self, generation_before: str, payload: str) -> None:
        self._redis.eval(
            _SET_IF_GENERATION_UNCHANGED,
            2,
            self._key,
            self._generation_key,
            generation_before,
            payload,
            self._ttl_seconds,
        )

    def invalidate(self) -> None:
        """Gọi sau mỗi lần ghi: tăng thế hệ rồi xoá dữ liệu đang cache."""
        self._redis.incr(self._generation_key)
        self._redis.delete(self._key)


def _to_text(value: object) -> str | None:
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else str(value)


class CachedList[T: BaseModel]:
    """Cache danh sách bản ghi của một tab (ví dụ mọi test case của một dự án).

    - `ttl_seconds` = 0 là tắt cache (luôn đọc Sheet).
    - Kho dữ liệu gọi `invalidate()` ngay sau mỗi lần ghi.
    - `read(..., bypass=True)` bỏ qua cache: dùng khi đang giữ khoá để "kiểm tra rồi ghi".
    """

    def __init__(self, redis: Redis, key: str, ttl_seconds: int, model: type[T]) -> None:
        self._cache = GenerationCache(redis, key, ttl_seconds) if ttl_seconds > 0 else None
        self._model = model

    @property
    def enabled(self) -> bool:
        return self._cache is not None

    def read(self, load: Callable[[], list[T]], *, bypass: bool = False) -> list[T]:
        if self._cache is None or bypass:
            return load()
        cached = self._cache.get()
        if cached is not None:
            return [self._model.model_validate(item) for item in json.loads(cached)]
        generation_before = self._cache.generation()
        items = load()
        payload = json.dumps([item.model_dump(mode="json") for item in items])
        self._cache.set_if_unchanged(generation_before, payload)
        return items

    def invalidate(self) -> None:
        if self._cache is not None:
            self._cache.invalidate()

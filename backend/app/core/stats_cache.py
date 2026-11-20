"""Cache `ProjectFacts` của từng project trong Redis (dùng bộ đếm thế hệ như `CachedList`).

Đọc cả tab TestCases và Results rất tốn lượt gọi Google, nên bản tóm tắt được nhớ 10 phút.
Mọi hàm ghi case hoặc kết quả phải gọi `invalidate_project_stats` để số liệu không bị cũ.
"""

from collections.abc import Callable

from redis import Redis

from app.core.cache import GenerationCache
from app.core.models.stats import ProjectFacts


def facts_cache_key(project_id: str) -> str:
    return f"cache:{project_id}:stats-facts"


class FactsCache:
    def __init__(self, redis: Redis, project_id: str, ttl_seconds: int) -> None:
        # ttl = 0 là tắt cache: luôn đọc Sheet
        self._cache = (
            GenerationCache(redis, facts_cache_key(project_id), ttl_seconds)
            if ttl_seconds > 0
            else None
        )

    def read(self, load: Callable[[], ProjectFacts]) -> ProjectFacts:
        if self._cache is None:
            return load()
        cached = self._cache.get()
        if cached is not None:
            return ProjectFacts.model_validate_json(cached)
        generation_before = self._cache.generation()
        facts = load()
        # Có ai ghi trong lúc đang đọc thì thế hệ đã đổi và bản cũ này không được lưu
        self._cache.set_if_unchanged(generation_before, facts.model_dump_json())
        return facts

    def invalidate(self) -> None:
        if self._cache is not None:
            self._cache.invalidate()


def invalidate_project_stats(redis: Redis, project_id: str) -> None:
    """Gọi sau mỗi lần ghi case hoặc kết quả của project."""
    GenerationCache(redis, facts_cache_key(project_id), 1).invalidate()

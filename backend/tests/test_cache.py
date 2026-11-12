import fakeredis

from app.core.cache import GenerationCache


def make_cache() -> GenerationCache:
    return GenerationCache(fakeredis.FakeRedis(), "cache:test", ttl_seconds=60)


def test_set_and_get_when_generation_unchanged() -> None:
    cache = make_cache()
    generation = cache.generation()

    cache.set_if_unchanged(generation, '["a"]')

    assert cache.get() == '["a"]'


def test_stale_payload_is_not_stored_after_invalidate() -> None:
    cache = make_cache()
    generation_before = cache.generation()  # bắt đầu đọc dữ liệu
    cache.invalidate()  # trong lúc đó có người ghi

    cache.set_if_unchanged(generation_before, '["cũ"]')

    assert cache.get() is None


def test_invalidate_removes_payload() -> None:
    cache = make_cache()
    cache.set_if_unchanged(cache.generation(), '["a"]')

    cache.invalidate()

    assert cache.get() is None

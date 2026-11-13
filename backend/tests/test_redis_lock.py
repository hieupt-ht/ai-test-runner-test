import threading
import time

import fakeredis
import pytest

from app.core.locks.redis_lock import LockTimeout, redis_lock

KEY = "lock:system:user:a@x.com"


def test_second_holder_waits_and_times_out() -> None:
    redis = fakeredis.FakeRedis()

    with redis_lock(redis, KEY):
        with pytest.raises(LockTimeout):
            with redis_lock(redis, KEY, wait_seconds=0.1):
                pass


def test_lock_released_after_block() -> None:
    redis = fakeredis.FakeRedis()

    with redis_lock(redis, KEY):
        pass

    with redis_lock(redis, KEY, wait_seconds=0.1):
        assert redis.exists(KEY) == 1
    assert redis.exists(KEY) == 0


def test_lock_released_when_block_raises() -> None:
    redis = fakeredis.FakeRedis()

    with pytest.raises(ValueError), redis_lock(redis, KEY):
        raise ValueError("lỗi trong lúc giữ khoá")

    assert redis.exists(KEY) == 0


def test_release_does_not_delete_someone_elses_lock() -> None:
    redis = fakeredis.FakeRedis()

    with redis_lock(redis, KEY, ttl_seconds=1):
        # Giả lập: khoá của mình hết hạn và người khác đã lấy khoá mới.
        redis.set(KEY, b"token-cua-nguoi-khac")

    assert redis.get(KEY) == b"token-cua-nguoi-khac"


def test_two_threads_never_inside_together() -> None:
    redis = fakeredis.FakeRedis()
    inside = {"now": 0, "max": 0}
    counter_guard = threading.Lock()

    def worker() -> None:
        for _ in range(20):
            with redis_lock(redis, KEY, wait_seconds=5):
                with counter_guard:
                    inside["now"] += 1
                    inside["max"] = max(inside["max"], inside["now"])
                time.sleep(0.001)
                with counter_guard:
                    inside["now"] -= 1

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert inside["max"] == 1


def test_default_ttl_outlasts_sheets_retries() -> None:
    # Mỗi lượt gọi Google có thể thử lại tới ~8 giây (0.5+1+2+4 + jitter), và trong khoá
    # thường có 3-4 lượt gọi. Khoá phải sống lâu hơn thế, nếu không người khác sẽ chen vào.
    redis = fakeredis.FakeRedis()

    with redis_lock(redis, KEY):
        remaining_ms = redis.pttl(KEY)

    assert remaining_ms > 45_000

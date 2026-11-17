import fakeredis

from app.core.login_throttle import LoginThrottle


def make(redis: fakeredis.FakeRedis) -> LoginThrottle:
    return LoginThrottle(redis, max_failures=5, lock_seconds=900)


def test_locks_after_five_failures(redis: fakeredis.FakeRedis) -> None:
    throttle = make(redis)
    for _ in range(5):
        throttle.record_failure("an@x.com")

    assert throttle.is_locked("an@x.com")


def test_not_locked_at_four(redis: fakeredis.FakeRedis) -> None:
    throttle = make(redis)
    for _ in range(4):
        throttle.record_failure("an@x.com")

    assert not throttle.is_locked("an@x.com")


def test_reset_clears_counter(redis: fakeredis.FakeRedis) -> None:
    throttle = make(redis)
    for _ in range(5):
        throttle.record_failure("an@x.com")

    throttle.reset("an@x.com")

    assert not throttle.is_locked("an@x.com")


def test_email_is_normalized(redis: fakeredis.FakeRedis) -> None:
    throttle = make(redis)
    for email in ["A@x.com", " a@X.com ", "a@x.com", "A@X.COM", "a@x.com "]:
        throttle.record_failure(email)

    assert throttle.is_locked("a@x.com")


def test_counter_has_ttl(redis: fakeredis.FakeRedis) -> None:
    throttle = make(redis)
    throttle.record_failure("an@x.com")

    ttl = redis.ttl("login_fail:an@x.com")
    assert 0 < ttl <= 900

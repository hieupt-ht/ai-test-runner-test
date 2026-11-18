import fakeredis
import pytest

from app.core.login_throttle import LoginThrottle
from app.core.passwords import hash_password
from app.core.repositories.users import UserRepository
from app.core.services.auth import LoginLockedError, authenticate
from tests.conftest import make_user


@pytest.fixture
def throttle(redis: fakeredis.FakeRedis) -> LoginThrottle:
    return LoginThrottle(redis, max_failures=5, lock_seconds=900)


def test_correct_password_returns_user(users: UserRepository, throttle: LoginThrottle) -> None:
    users.create(make_user("an@x.com"), password_hash=hash_password("mat-khau-1"))

    user = authenticate(users, "  An@X.com", "mat-khau-1", throttle)

    assert user is not None
    assert user.email == "an@x.com"


def test_wrong_password_returns_none_and_counts(
    users: UserRepository, throttle: LoginThrottle
) -> None:
    users.create(make_user("an@x.com"), password_hash=hash_password("mat-khau-1"))

    assert authenticate(users, "an@x.com", "sai", throttle) is None
    for _ in range(4):
        authenticate(users, "an@x.com", "sai", throttle)
    assert throttle.is_locked("an@x.com")


def test_unknown_email_returns_none_and_counts(
    users: UserRepository, throttle: LoginThrottle
) -> None:
    for _ in range(5):
        assert authenticate(users, "la@x.com", "gi-do-123", throttle) is None

    assert throttle.is_locked("la@x.com")


def test_inactive_user_returns_none(users: UserRepository, throttle: LoginThrottle) -> None:
    users.create(make_user("an@x.com", active=False), password_hash=hash_password("mat-khau-1"))

    assert authenticate(users, "an@x.com", "mat-khau-1", throttle) is None


def test_user_without_password_returns_none(
    users: UserRepository, throttle: LoginThrottle
) -> None:
    users.create(make_user("an@x.com"))

    assert authenticate(users, "an@x.com", "", throttle) is None
    assert authenticate(users, "an@x.com", "mat-khau-1", throttle) is None


def test_locked_raises_even_with_correct_password(
    users: UserRepository, throttle: LoginThrottle
) -> None:
    users.create(make_user("an@x.com"), password_hash=hash_password("mat-khau-1"))
    for _ in range(5):
        authenticate(users, "an@x.com", "sai", throttle)

    with pytest.raises(LoginLockedError):
        authenticate(users, "an@x.com", "mat-khau-1", throttle)


def test_success_resets_counter(users: UserRepository, throttle: LoginThrottle) -> None:
    users.create(make_user("an@x.com"), password_hash=hash_password("mat-khau-1"))
    for _ in range(4):
        authenticate(users, "an@x.com", "sai", throttle)

    assert authenticate(users, "an@x.com", "mat-khau-1", throttle) is not None
    for _ in range(4):
        authenticate(users, "an@x.com", "sai", throttle)

    assert not throttle.is_locked("an@x.com")

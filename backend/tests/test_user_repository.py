import json

import fakeredis
import pytest

from app.core.locks.redis_lock import LockTimeout, redis_lock
from app.core.models.user import Role
from app.core.repositories.users import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserRepository,
)
from tests.conftest import SYSTEM_SHEET_ID, make_user
from tests.fakes import FakeSheetsGateway


def users_tab(gateway: FakeSheetsGateway) -> list[list[str]]:
    return gateway.data[SYSTEM_SHEET_ID]["Users"]


def test_create_then_get_normalizes_email(users: UserRepository) -> None:
    users.create(make_user("  An@X.com "))

    found = users.get("  AN@x.COM")

    assert found is not None
    assert found.email == "an@x.com"


def test_active_is_stored_as_true_false_text(
    users: UserRepository, gateway: FakeSheetsGateway
) -> None:
    users.create(make_user("an@x.com", active=False))

    assert users_tab(gateway)[1][3] == "FALSE"


def test_create_duplicate_raises(users: UserRepository) -> None:
    users.create(make_user("an@x.com"))

    with pytest.raises(UserAlreadyExistsError):
        users.create(make_user("AN@x.com"))


def test_update_finds_row_by_email_even_after_rows_inserted_above(
    users: UserRepository, gateway: FakeSheetsGateway
) -> None:
    users.create(make_user("an@x.com", name="An"))
    users.create(make_user("binh@x.com", name="Bình"))
    # Ai đó chèn tay một dòng ngay dưới tiêu đề: số dòng của Bình đổi từ 3 thành 4.
    users_tab(gateway).insert(1, ["chi@x.com", "Chi", "VIEWER", "TRUE", "2026-11-12T00:00:00Z"])

    users.update(make_user("binh@x.com", name="Bình Trần", role=Role.QA_LEAD))

    assert users_tab(gateway)[3][:3] == ["binh@x.com", "Bình Trần", "QA_LEAD"]
    assert users_tab(gateway)[2][1] == "An"


def test_update_unknown_user_raises(users: UserRepository) -> None:
    with pytest.raises(UserNotFoundError):
        users.update(make_user("khong-co@x.com"))


def test_list_uses_cache_then_invalidates_on_write(
    users: UserRepository, gateway: FakeSheetsGateway
) -> None:
    users.create(make_user("an@x.com"))
    gateway.calls.clear()

    users.list_all()
    users.list_all()
    assert gateway.calls.count("Users") == 1

    users.update(make_user("an@x.com", name="An mới"))
    gateway.calls.clear()

    assert users.list_all()[0].name == "An mới"
    assert gateway.calls.count("Users") == 1


def test_create_takes_lock(users: UserRepository, redis: fakeredis.FakeRedis) -> None:
    with redis_lock(redis, "lock:system:users"):
        with pytest.raises(LockTimeout):
            users.create(make_user("an@x.com"))


def test_is_empty(users: UserRepository) -> None:
    assert users.is_empty()
    users.create(make_user("an@x.com"))
    assert not users.is_empty()


def test_cache_holds_json_list(users: UserRepository, redis: fakeredis.FakeRedis) -> None:
    users.create(make_user("an@x.com"))
    users.list_all()

    cached = redis.get("cache:users")

    assert cached is not None
    assert json.loads(cached)[0]["email"] == "an@x.com"


def test_stale_read_does_not_refill_cache_after_a_write(
    users: UserRepository, gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis
) -> None:
    users.create(make_user("an@x.com"))
    original_get_values = gateway.get_values

    def get_values_with_concurrent_write(spreadsheet_id: str, a1_range: str) -> list[list[str]]:
        rows = original_get_values(spreadsheet_id, a1_range)
        if a1_range == "Users":
            # Trong lúc request A đang đọc Sheet, Admin B khoá user này
            gateway.get_values = original_get_values  # type: ignore[method-assign]
            users.update(make_user("an@x.com", active=False))
        return rows

    gateway.get_values = get_values_with_concurrent_write  # type: ignore[method-assign]
    users.list_all()  # đọc được dữ liệu CŨ (active=True)

    assert redis.get("cache:users") is None  # không được ghi dữ liệu cũ vào cache
    found = users.get("an@x.com")
    assert found is not None and not found.active


def test_writes_take_one_lock_for_the_whole_users_tab(
    users: UserRepository, redis: fakeredis.FakeRedis
) -> None:
    users.create(make_user("an@x.com"))

    # Đang có người thêm user khác (giữ khoá cả tab) → sửa user "an" phải chờ
    with redis_lock(redis, "lock:system:users"):
        with pytest.raises(LockTimeout):
            users.update(make_user("an@x.com", name="An mới"))

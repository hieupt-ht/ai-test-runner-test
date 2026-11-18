import fakeredis

from app.api.sessions import SessionStore


def test_delete_all_for_removes_every_session_of_that_user_only(
    redis: fakeredis.FakeRedis,
) -> None:
    store = SessionStore(redis, ttl_seconds=3600)
    a1, a2 = store.create("an@x.com"), store.create("an@x.com")
    b1 = store.create("binh@x.com")

    store.delete_all_for("an@x.com")

    assert store.get_email(a1) is None
    assert store.get_email(a2) is None
    assert store.get_email(b1) == "binh@x.com"


def test_delete_all_for_unknown_user_is_noop(redis: fakeredis.FakeRedis) -> None:
    SessionStore(redis, ttl_seconds=3600).delete_all_for("khong-co@x.com")


def test_delete_all_for_normalizes_email(redis: fakeredis.FakeRedis) -> None:
    store = SessionStore(redis, ttl_seconds=3600)
    session_id = store.create("an@x.com")

    store.delete_all_for("  An@X.com ")

    assert store.get_email(session_id) is None


def test_dung_phien_thi_gia_han_ca_danh_sach_phien_cua_user() -> None:
    """Phiên "trượt" mà danh sách phiên hết hạn sớm thì đổi mật khẩu sẽ sót phiên cũ."""
    redis = fakeredis.FakeRedis()
    store = SessionStore(redis, ttl_seconds=3600)
    session_id = store.create("a@x.com")
    redis.expire("user_sessions:a@x.com", 10)  # giả lập đã trôi qua gần hết hạn

    store.get_email(session_id)

    assert redis.ttl("user_sessions:a@x.com") > 3000

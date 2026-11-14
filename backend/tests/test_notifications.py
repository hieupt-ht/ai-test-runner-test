import fakeredis

from app.core.notifications import NotificationStore


def test_add_then_list_newest_first() -> None:
    store = NotificationStore(fakeredis.FakeRedis())

    store.add("a@example.com", type="member", title="Đầu", link="/one")
    store.add("a@example.com", type="member", title="Sau", link="/two")

    assert [item.title for item in store.list("a@example.com")] == ["Sau", "Đầu"]


def test_unread_count_and_mark_read() -> None:
    store = NotificationStore(fakeredis.FakeRedis())
    store.add("a@example.com", type="member", title="Mời", link="/one")

    item = store.list("a@example.com")[0]

    assert store.unread_count("a@example.com") == 1
    assert store.mark_read("a@example.com", item.id) is True
    assert store.unread_count("a@example.com") == 0


def test_mark_all_read() -> None:
    store = NotificationStore(fakeredis.FakeRedis())
    store.add("a@example.com", type="member", title="Một", link="/one")
    store.add("a@example.com", type="member", title="Hai", link="/two")

    store.mark_all_read("a@example.com")

    assert store.unread_count("a@example.com") == 0


def test_trims_to_max_items() -> None:
    store = NotificationStore(fakeredis.FakeRedis(), max_items=100)

    for index in range(105):
        store.add("a@example.com", type="member", title=str(index), link="/one")

    items = store.list("a@example.com")
    assert len(items) == 100
    assert items[-1].title == "5"


def test_emails_are_isolated() -> None:
    store = NotificationStore(fakeredis.FakeRedis())
    store.add("A@example.com", type="member", title="Của A", link="/one")

    assert [item.title for item in store.list(" a@EXAMPLE.com ")] == ["Của A"]
    assert store.list("b@example.com") == []


def test_mark_read_unknown_id_returns_false() -> None:
    store = NotificationStore(fakeredis.FakeRedis())

    assert store.mark_read("a@example.com", "missing") is False

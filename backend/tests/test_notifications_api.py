import fakeredis
from fastapi.testclient import TestClient

from app.core.notifications import NotificationStore


def test_list_empty_returns_zero_unread(client_as_tester: TestClient) -> None:
    response = client_as_tester.get("/api/notifications")

    assert response.status_code == 200
    assert response.json() == {"items": [], "unread": 0}


def test_list_returns_only_my_notifications(
    client_as_tester: TestClient, redis: fakeredis.FakeRedis
) -> None:
    store = NotificationStore(redis)
    store.add("tester@x.com", type="member", title="Của tôi", link="/projects/a")
    store.add("other@x.com", type="member", title="Của người khác", link="/projects/b")

    response = client_as_tester.get("/api/notifications")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Của tôi"]
    assert response.json()["unread"] == 1


def test_mark_read_updates_unread(
    client_as_tester: TestClient, redis: fakeredis.FakeRedis
) -> None:
    store = NotificationStore(redis)
    store.add("tester@x.com", type="member", title="Mời", link="/projects/a")
    notification_id = store.list("tester@x.com")[0].id

    response = client_as_tester.post(f"/api/notifications/{notification_id}/read")

    assert response.status_code == 204
    assert client_as_tester.get("/api/notifications").json()["unread"] == 0


def test_mark_other_users_notification_returns_404(
    client_as_tester: TestClient, redis: fakeredis.FakeRedis
) -> None:
    store = NotificationStore(redis)
    store.add("other@x.com", type="member", title="Riêng", link="/projects/b")
    notification_id = store.list("other@x.com")[0].id

    response = client_as_tester.post(f"/api/notifications/{notification_id}/read")

    assert response.status_code == 404
    assert response.json() == {"detail": "Không tìm thấy thông báo"}
    assert store.unread_count("other@x.com") == 1


def test_mark_all_read(client_as_tester: TestClient, redis: fakeredis.FakeRedis) -> None:
    store = NotificationStore(redis)
    store.add("tester@x.com", type="member", title="Mời", link="/projects/a")

    response = client_as_tester.post("/api/notifications/read-all")

    assert response.status_code == 204
    assert store.unread_count("tester@x.com") == 0


def test_requires_login(client: TestClient) -> None:
    for method, path in (
        ("GET", "/api/notifications"),
        ("POST", "/api/notifications/read-all"),
        ("POST", "/api/notifications/some-id/read"),
    ):
        assert client.request(method, path).status_code == 401

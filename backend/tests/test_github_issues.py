"""Kiểm tra các thao tác issue qua GitHub REST giả."""

import httpx
import pytest

from app.core.github.client import GitHubAppClient, GitHubError
from tests.test_github_client import APP_ID, NOW, PRIVATE_PEM


def make_client(handler: httpx.MockTransport) -> GitHubAppClient:
    return GitHubAppClient(
        APP_ID,
        PRIVATE_PEM,
        http=httpx.Client(transport=handler, base_url="https://api.github.com"),
        now=lambda: NOW,
    )


def server(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/repos/org/web/installation":
        return httpx.Response(200, json={"id": 1})
    if request.url.path == "/app/installations/1/access_tokens":
        return httpx.Response(201, json={"token": "token-1", "expires_at": "2027-01-15T09:00:00Z"})
    if request.url.path == "/repos/org/web/issues" and request.method == "GET":
        return httpx.Response(
            200,
            json=[
                {
                    "number": 8,
                    "html_url": "https://github.com/org/web/issues/8",
                    "state": "open",
                    "title": "B",
                    "labels": [{"name": "tc:TC-000001"}],
                },
                {
                    "number": 3,
                    "html_url": "https://github.com/org/web/issues/3",
                    "state": "closed",
                    "title": "A",
                    "labels": [{"name": "tc:TC-000001"}],
                },
            ],
        )
    return httpx.Response(404)


def test_find_issue_by_label_returns_lowest_number_including_closed() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return server(request)

    issue = make_client(httpx.MockTransport(handle)).find_issue_by_label("org/web", "tc:TC-000001")

    assert issue is not None and issue.number == 3 and issue.state == "closed"
    assert requests[-1].url.params["state"] == "all"
    assert requests[-1].url.params["labels"] == "tc:TC-000001"
    assert requests[-1].headers["Authorization"] == "Bearer token-1"


def test_find_issue_by_label_none_when_missing() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/web/issues":
            return httpx.Response(200, json=[])
        return server(request)

    assert (
        make_client(httpx.MockTransport(handle)).find_issue_by_label("org/web", "missing") is None
    )


def test_create_issue_posts_title_body_labels() -> None:
    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/web/issues" and request.method == "POST":
            sent.append(request)
            return httpx.Response(
                201,
                json={
                    "number": 4,
                    "html_url": "https://github.com/org/web/issues/4",
                    "state": "open",
                    "title": "Tiêu đề",
                    "labels": [{"name": "test-case"}],
                },
            )
        return server(request)

    issue = make_client(httpx.MockTransport(handle)).create_issue(
        "org/web", title="Tiêu đề", body="Nội dung", labels=["test-case"]
    )

    assert issue.number == 4 and issue.labels == ["test-case"]
    assert sent[0].read().decode() == '{"title":"Tiêu đề","body":"Nội dung","labels":["test-case"]}'


def test_update_issue_patches_state_and_fields() -> None:
    sent: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues/4"):
            sent.append(request)
            return httpx.Response(
                200,
                json={
                    "number": 4,
                    "html_url": "https://github.com/org/web/issues/4",
                    "state": "closed",
                    "title": "Mới",
                    "labels": [],
                },
            )
        return server(request)

    issue = make_client(httpx.MockTransport(handle)).update_issue(
        "org/web", 4, title="Mới", body="B", labels=[], state="closed"
    )

    assert issue.state == "closed"
    assert sent[0].method == "PATCH"
    assert b'"state":"closed"' in sent[0].read()


def test_ensure_label_ignores_already_exists() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/web/labels":
            return httpx.Response(422, json={"errors": [{"code": "already_exists"}]})
        return server(request)

    make_client(httpx.MockTransport(handle)).ensure_label("org/web", "test-case")


def test_issue_calls_use_installation_token_of_the_repo() -> None:
    auth: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/other/app/installation":
            return httpx.Response(200, json={"id": 2})
        if path == "/app/installations/2/access_tokens":
            return httpx.Response(
                201, json={"token": "token-2", "expires_at": "2027-01-15T09:00:00Z"}
            )
        if path == "/repos/other/app/issues":
            auth.append(request.headers["Authorization"])
            return httpx.Response(200, json=[])
        return server(request)

    make_client(httpx.MockTransport(handle)).find_issue_by_label("other/app", "tc:TC-000001")

    assert auth == ["Bearer token-2"]


def test_github_error_on_403_rate_limit_has_vietnamese_message() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/web/issues":
            return httpx.Response(403)
        return server(request)

    with pytest.raises(GitHubError, match="giới hạn"):
        make_client(httpx.MockTransport(handle)).find_issue_by_label("org/web", "tc:TC-000001")


def assignees_server(returned: list[str], sent: list[httpx.Request]):  # type: ignore[no-untyped-def]
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/org/web/issues/5/assignees":
            sent.append(request)
            return httpx.Response(
                201, json={"number": 5, "assignees": [{"login": name} for name in returned]}
            )
        return server(request)

    return handle


def test_add_assignees_posts_to_assignees_endpoint() -> None:
    sent: list[httpx.Request] = []
    client = make_client(httpx.MockTransport(assignees_server(["nguyenvana"], sent)))

    client.add_assignees("org/web", 5, ["nguyenvana"])

    assert sent[0].method == "POST"
    assert b'"assignees":["nguyenvana"]' in sent[0].read()


def test_add_assignees_errors_when_github_silently_ignores_the_user() -> None:
    # GitHub trả 201 nhưng bỏ qua người không có quyền: phải tự so sánh danh sách trả về
    client = make_client(httpx.MockTransport(assignees_server([], [])))

    with pytest.raises(GitHubError, match="Không gán được @nguyenvana"):
        client.add_assignees("org/web", 5, ["nguyenvana"])


def test_add_assignees_compares_names_case_insensitively() -> None:
    client = make_client(httpx.MockTransport(assignees_server(["NguyenVanA"], [])))
    client.add_assignees("org/web", 5, ["nguyenvana"])

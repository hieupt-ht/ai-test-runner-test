"""DriveClient: tạo thư mục theo project, tải lên, chia sẻ, xoá; không lộ secret."""

import io
import json
import threading
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core.media.drive import DriveClient, DriveError
from app.core.models.media import Media, MediaKind

API = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
SESSION = "https://upload.example/session/1"
SECRET = "client-secret-xyz"
REFRESH = "refresh-token-xyz"


class FakeDriveApi:
    """Giả lập các lệnh Drive mà DriveClient dùng; ghi lại mọi request để test xem."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.folders: dict[tuple[str, str], str] = {}  # (tên, cha) -> id
        self.unauthorized_once = 0  # số lần đầu trả 401 cho lệnh Drive
        self.always_unauthorized = False
        self.token_fails = False
        self.token_calls = 0
        self.upload_status = 200
        self.share_status = 200
        self.delete_status = 204
        self.create_delay = 0.0
        self.uploaded: list[bytes] = []
        self._lock = threading.Lock()
        self._counter = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            self.requests.append(request)
        url = str(request.url)
        if url.startswith("https://oauth2.googleapis.com/token"):
            self.token_calls += 1
            if self.token_fails:
                return httpx.Response(400, json={"error": "invalid_grant"})
            token = f"at{self.token_calls}"
            return httpx.Response(200, json={"access_token": token, "expires_in": 3600})
        if url.startswith(SESSION):
            self.uploaded.append(request.read())
            if self.upload_status != 200:
                return httpx.Response(self.upload_status)
            return httpx.Response(200, json={"id": "FILE1"})
        if self.always_unauthorized:
            return httpx.Response(401)
        if self.unauthorized_once > 0:
            self.unauthorized_once -= 1
            return httpx.Response(401)
        return self._drive(request, url)

    def _drive(self, request: httpx.Request, url: str) -> httpx.Response:
        path = urlparse(url).path
        if request.method == "GET" and path == "/drive/v3/files":
            query = parse_qs(urlparse(url).query)["q"][0]
            for (name, parent), folder_id in self.folders.items():
                if f"'{parent}' in parents" in query and f"name='{name}'" in query:
                    return httpx.Response(200, json={"files": [{"id": folder_id}]})
            return httpx.Response(200, json={"files": []})
        if request.method == "POST" and path == "/drive/v3/files":
            time.sleep(self.create_delay)
            body = json.loads(request.content)
            with self._lock:
                self._counter += 1
                folder_id = f"F{self._counter}"
                self.folders[(body["name"], body["parents"][0])] = folder_id
            return httpx.Response(200, json={"id": folder_id})
        if request.method == "POST" and path == "/upload/drive/v3/files":
            return httpx.Response(200, headers={"Location": SESSION})
        if request.method == "POST" and path.endswith("/permissions"):
            return httpx.Response(self.share_status, json={})
        if request.method == "DELETE":
            return httpx.Response(self.delete_status)
        return httpx.Response(500)

    def calls(self, method: str, path: str) -> list[httpx.Request]:
        return [
            r for r in self.requests
            if r.method == method and urlparse(str(r.url)).path == path
        ]


def make_client(api: FakeDriveApi, root: str = "") -> DriveClient:
    return DriveClient(
        "client-id",
        SECRET,
        REFRESH,
        root,
        http=httpx.Client(transport=httpx.MockTransport(api.handler)),
        now=lambda: 1_700_000_000,
    )


def upload(client: DriveClient, project: str = "PRJ-0001", name: str = "anh.PNG") -> Media:
    data = io.BytesIO(b"abc")
    return client.upload(project, "guide", MediaKind.IMAGE, name, "image/png", data, 3)


def test_upload_creates_project_folders_then_uploads_and_shares() -> None:
    api = FakeDriveApi()

    media = upload(make_client(api))

    names = [name for (name, _parent) in api.folders]
    assert names == ["ai-test-runner", "PRJ-0001", "guide"]
    assert media.url == "https://drive.google.com/file/d/FILE1/view"
    assert media.public_id == "FILE1"
    assert media.kind == MediaKind.IMAGE
    assert api.uploaded == [b"abc"]
    metadata = json.loads(api.calls("POST", "/upload/drive/v3/files")[0].content)
    root = api.folders[("ai-test-runner", "root")]
    project = api.folders[("PRJ-0001", root)]
    assert metadata["parents"] == [api.folders[("guide", project)]]
    assert metadata["name"].endswith(".png") and "anh" not in metadata["name"]
    permission = json.loads(api.calls("POST", "/drive/v3/files/FILE1/permissions")[0].content)
    assert permission == {"role": "reader", "type": "anyone"}


def test_folder_ids_are_cached_between_uploads() -> None:
    api = FakeDriveApi()
    client = make_client(api)

    upload(client)
    gets_before = len(api.calls("GET", "/drive/v3/files"))
    creates_before = len(api.calls("POST", "/drive/v3/files"))
    upload(client)

    assert len(api.calls("GET", "/drive/v3/files")) == gets_before
    assert len(api.calls("POST", "/drive/v3/files")) == creates_before


def test_existing_folder_is_reused_not_created() -> None:
    api = FakeDriveApi()
    api.folders[("ai-test-runner", "root")] = "EXIST1"

    upload(make_client(api))

    created = [json.loads(r.content)["name"] for r in api.calls("POST", "/drive/v3/files")]
    assert created == ["PRJ-0001", "guide"]


def test_root_folder_id_replaces_default_root_folder() -> None:
    api = FakeDriveApi()

    upload(make_client(api, root="MYROOT"))

    assert [name for (name, _p) in api.folders] == ["PRJ-0001", "guide"]
    assert api.folders[("PRJ-0001", "MYROOT")]


def test_folder_search_escapes_quotes_in_names() -> None:
    api = FakeDriveApi()

    upload(make_client(api), project="PRJ'1\\x")

    gets = api.calls("GET", "/drive/v3/files")
    queries = [parse_qs(urlparse(str(r.url)).query)["q"][0] for r in gets]
    assert any("name='PRJ\\'1\\\\x'" in q for q in queries)


def test_access_token_is_reused() -> None:
    api = FakeDriveApi()
    client = make_client(api)

    upload(client)
    upload(client)

    assert api.token_calls == 1


def test_refreshes_access_token_once_on_401() -> None:
    api = FakeDriveApi()
    api.unauthorized_once = 1

    media = upload(make_client(api))

    assert media.public_id == "FILE1"
    assert api.token_calls == 2


def test_persistent_401_stops_after_one_retry() -> None:
    api = FakeDriveApi()
    api.always_unauthorized = True

    with pytest.raises(DriveError):
        upload(make_client(api))

    assert api.token_calls == 2


def test_token_error_message_has_no_secret() -> None:
    api = FakeDriveApi()
    api.token_fails = True

    with pytest.raises(DriveError) as caught:
        upload(make_client(api))

    assert SECRET not in str(caught.value) and REFRESH not in str(caught.value)


def test_concurrent_first_uploads_create_one_folder_each() -> None:
    api = FakeDriveApi()
    api.create_delay = 0.05
    client = make_client(api)
    errors: list[Exception] = []

    def run() -> None:
        try:
            upload(client)
        except Exception as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=run) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(api.folders) == 3  # ai-test-runner, PRJ-0001, guide — mỗi thư mục đúng một lần


def test_upload_failure_raises_drive_error() -> None:
    api = FakeDriveApi()
    api.upload_status = 503

    with pytest.raises(DriveError, match="Không tải được lên Google Drive"):
        upload(make_client(api))


def test_share_failure_deletes_the_uploaded_file() -> None:
    api = FakeDriveApi()
    api.share_status = 403

    with pytest.raises(DriveError):
        upload(make_client(api))

    assert api.calls("DELETE", "/drive/v3/files/FILE1")


def test_destroy_deletes_by_id_and_ignores_404() -> None:
    api = FakeDriveApi()
    client = make_client(api)

    client.destroy("FILE1", MediaKind.IMAGE)
    api.delete_status = 404
    client.destroy("FILE1", MediaKind.IMAGE)  # đã xoá rồi thì không báo lỗi

    assert len(api.calls("DELETE", "/drive/v3/files/FILE1")) == 2

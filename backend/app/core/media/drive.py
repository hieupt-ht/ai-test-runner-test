"""Google Drive: tải ảnh/video lên thư mục riêng của từng project, chia sẻ link và xoá file.

Đăng nhập bằng OAuth của tài khoản Gmail chủ dự án (refresh token đặt trong `.env`).
Secret và token chỉ nằm trong đối tượng này; lỗi trả ra ngoài không bao giờ chứa chúng.
"""

import logging
import re
import secrets
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any, BinaryIO

import httpx

from app.core.media.cloudinary import Purpose
from app.core.models.media import DRIVE_PREFIX, Media, MediaKind

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
FILES_URL = "https://www.googleapis.com/drive/v3/files"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER_MIME = "application/vnd.google-apps.folder"
DEFAULT_ROOT_NAME = "ai-test-runner"
CHUNK_BYTES = 1024 * 1024
_SAFE_SUFFIX = re.compile(r"^\.[a-z0-9]{1,5}$")


class DriveError(Exception):
    """Lỗi Drive, nội dung đã viết sẵn bằng tiếng Việt và không chứa secret/token."""


def _escape(value: str) -> str:
    """Thoát `\\` và `'` để tên thư mục nằm an toàn trong câu truy vấn của Drive."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _chunks(data: BinaryIO) -> Iterator[bytes]:
    """Đọc từng khúc để video lớn không phải nằm hết trong RAM."""
    while chunk := data.read(CHUNK_BYTES):
        yield chunk


def _file_name(filename: str) -> str:
    """Tên file trên Drive: chuỗi ngẫu nhiên + đuôi gốc (không dùng tên gốc cho khỏi ký tự lạ)."""
    dot = filename.rfind(".")
    suffix = filename[dot:].lower() if dot >= 0 else ""
    return secrets.token_urlsafe(12) + (suffix if _SAFE_SUFFIX.match(suffix) else "")


class DriveClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        root_folder_id: str = "",
        *,
        http: httpx.Client | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._root_folder_id = root_folder_id
        self._http = http or httpx.Client(timeout=120)
        self._now = now
        self._access_token = ""
        self._expires_at = 0.0
        self._folder_ids: dict[tuple[str, ...], str] = {}
        self._folder_lock = threading.RLock()  # _folder tự gọi lại chính nó

    # ----- Đăng nhập -----

    def _token(self, *, force: bool = False) -> str:
        if not force and self._access_token and self._now() < self._expires_at - 60:
            return self._access_token
        try:
            response = self._http.post(
                TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        except httpx.HTTPError:
            raise DriveError("Không kết nối được tới Google để đăng nhập Drive") from None
        if response.status_code != 200:
            raise DriveError("Google từ chối đăng nhập Drive, hãy kiểm tra cấu hình GOOGLE_OAUTH_*")
        body = response.json()
        self._access_token = body["access_token"]
        self._expires_at = self._now() + float(body.get("expires_in", 3600))
        return self._access_token

    def _call(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Gọi API Drive; gặp 401 thì làm mới token và thử lại đúng một lần."""
        for attempt in range(2):
            headers = {"Authorization": f"Bearer {self._token(force=attempt == 1)}"}
            try:
                response = self._http.request(method, url, headers=headers, **kwargs)
            except httpx.HTTPError:
                raise DriveError("Không tải được lên Google Drive") from None
            if response.status_code != 401:
                return response
        raise DriveError("Google từ chối quyền truy cập Drive, hãy cấp quyền lại")

    # ----- Thư mục -----

    def _folder(self, parts: tuple[str, ...]) -> str:
        """ID thư mục theo đường dẫn; tìm trước, chưa có mới tạo, rồi nhớ lại."""
        with self._folder_lock:
            if parts in self._folder_ids:
                return self._folder_ids[parts]
            parent = self._folder(parts[:-1]) if len(parts) > 1 else self._root_parent()
            folder_id = self._find_folder(parts[-1], parent)
            if folder_id is None:
                folder_id = self._create_folder(parts[-1], parent)
            self._folder_ids[parts] = folder_id
            return folder_id

    def _root_parent(self) -> str:
        return self._root_folder_id or "root"

    def _find_folder(self, name: str, parent: str) -> str | None:
        query = (
            f"name='{_escape(name)}' and '{_escape(parent)}' in parents"
            f" and mimeType='{FOLDER_MIME}' and trashed=false"
        )
        response = self._call(
            "GET", FILES_URL, params={"q": query, "fields": "files(id)", "pageSize": 1}
        )
        if response.status_code != 200:
            raise DriveError("Không tải được lên Google Drive")
        files = response.json().get("files", [])
        return str(files[0]["id"]) if files else None

    def _create_folder(self, name: str, parent: str) -> str:
        response = self._call(
            "POST", FILES_URL, json={"name": name, "mimeType": FOLDER_MIME, "parents": [parent]}
        )
        if response.status_code != 200:
            raise DriveError("Không tải được lên Google Drive")
        return str(response.json()["id"])

    def _folder_path(self, project_id: str, purpose: Purpose) -> tuple[str, ...]:
        if self._root_folder_id:
            return (project_id, purpose)
        return (DEFAULT_ROOT_NAME, project_id, purpose)

    # ----- Tải lên / xoá -----

    def upload(
        self,
        project_id: str,
        purpose: Purpose,
        kind: MediaKind,
        filename: str,
        content_type: str,
        data: BinaryIO,
        size: int,
    ) -> Media:
        """Đẩy một file lên thư mục của project, cho "ai có link đều xem", trả về `Media`."""
        parent = self._folder(self._folder_path(project_id, purpose))
        session_url = self._start_session(parent, filename)
        try:
            sent = self._http.put(
                session_url,
                content=_chunks(data),
                headers={"Content-Type": content_type, "Content-Length": str(size)},
            )
        except httpx.HTTPError:
            raise DriveError("Không tải được lên Google Drive") from None
        if sent.status_code not in (200, 201):
            raise DriveError("Không tải được lên Google Drive")
        file_id = str(sent.json()["id"])
        self._share(file_id)
        return Media(kind=kind, url=f"{DRIVE_PREFIX}{file_id}/view", public_id=file_id)

    def _start_session(self, parent: str, filename: str) -> str:
        response = self._call(
            "POST",
            UPLOAD_URL,
            params={"uploadType": "resumable", "fields": "id"},
            json={"name": _file_name(filename), "parents": [parent]},
        )
        location = response.headers.get("Location")
        if response.status_code != 200 or not location:
            raise DriveError("Không tải được lên Google Drive")
        return str(location)

    def _share(self, file_id: str) -> None:
        """Cho ai có link cũng xem được; lỗi thì xoá file vừa tải để không để lại file mồ côi."""
        response = self._call(
            "POST", f"{FILES_URL}/{file_id}/permissions", json={"role": "reader", "type": "anyone"}
        )
        if response.status_code != 200:
            try:
                self.destroy(file_id, MediaKind.IMAGE)
            except Exception:
                logger.warning("Không xoá được file Drive %s", file_id, exc_info=True)
            raise DriveError("Không chia sẻ được file trên Google Drive")

    def destroy(self, public_id: str, kind: MediaKind) -> None:
        """Xoá file theo ID; file đã mất (404) thì coi như xong."""
        response = self._call("DELETE", f"{FILES_URL}/{public_id}")
        if response.status_code not in (200, 204, 404):
            raise DriveError("Không xoá được file trên Google Drive")

"""Cloudinary: ký upload cho trình duyệt/Codex và xoá file không dùng nữa.

`api_secret` chỉ nằm trong đối tượng này (ở backend). Thứ gửi ra ngoài chỉ có chữ ký đã tính.
"""

import hashlib
import logging
import secrets
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel

from app.core.models.media import Media, MediaKind

logger = logging.getLogger(__name__)

API_URL = "https://api.cloudinary.com/v1_1"
ALLOWED_FORMATS = {
    MediaKind.IMAGE: "jpg,jpeg,png,webp,gif",
    MediaKind.VIDEO: "mp4,mov,webm",
}
MAX_BYTES = {
    MediaKind.IMAGE: 10 * 1024 * 1024,  # ảnh ≤ 10MB
    MediaKind.VIDEO: 100 * 1024 * 1024,  # video ≤ 100MB
}

Purpose = Literal["guide", "evidence"]


class SignedUpload(BaseModel):
    """Mọi thứ client cần để đẩy thẳng một file lên Cloudinary (không có secret)."""

    cloud_name: str
    api_key: str
    timestamp: int
    signature: str
    folder: str
    public_id: str
    allowed_formats: str
    resource_type: Literal["image", "video"]
    max_bytes: int
    upload_url: str


def _signature(params: dict[str, str | int], api_secret: str) -> str:
    """Quy tắc của Cloudinary: sắp tên tham số, nối `k=v` bằng `&`, thêm secret rồi SHA-1."""
    raw = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return hashlib.sha1(f"{raw}{api_secret}".encode()).hexdigest()


class CloudinarySigner:
    def __init__(
        self,
        cloud_name: str,
        api_key: str,
        api_secret: str,
        *,
        now: Callable[[], float] = time.time,
        token: Callable[[int], str] = secrets.token_urlsafe,
    ) -> None:
        self._cloud_name = cloud_name
        self._api_key = api_key
        self._api_secret = api_secret
        self._now = now
        self._token = token

    def sign(self, project_id: str, purpose: Purpose, kind: MediaKind) -> SignedUpload:
        folder = f"ai-test-runner/{project_id}/{purpose}"
        public_id = self._token(16)
        timestamp = int(self._now())
        formats = ALLOWED_FORMATS[kind]
        signature = _signature(
            {
                "allowed_formats": formats,
                "folder": folder,
                "public_id": public_id,
                "timestamp": timestamp,
            },
            self._api_secret,
        )
        return SignedUpload(
            cloud_name=self._cloud_name,
            api_key=self._api_key,
            timestamp=timestamp,
            signature=signature,
            folder=folder,
            public_id=public_id,
            allowed_formats=formats,
            resource_type=kind.value,
            max_bytes=MAX_BYTES[kind],
            upload_url=f"{API_URL}/{self._cloud_name}/{kind.value}/upload",
        )


class MediaDestroyer(Protocol):
    def destroy(self, public_id: str, kind: MediaKind) -> None: ...


class CloudinaryClient:
    """Gọi API quản trị của Cloudinary (hiện chỉ có xoá file)."""

    def __init__(
        self,
        cloud_name: str,
        api_key: str,
        api_secret: str,
        *,
        now: Callable[[], float] = time.time,
        http: httpx.Client | None = None,
    ) -> None:
        self._cloud_name = cloud_name
        self._api_key = api_key
        self._api_secret = api_secret
        self._now = now
        self._http = http or httpx.Client(timeout=20)

    def destroy(self, public_id: str, kind: MediaKind) -> None:
        timestamp = int(self._now())
        signature = _signature({"public_id": public_id, "timestamp": timestamp}, self._api_secret)
        response = self._http.post(
            f"{API_URL}/{self._cloud_name}/{kind.value}/destroy",
            data={
                "public_id": public_id,
                "timestamp": timestamp,
                "api_key": self._api_key,
                "signature": signature,
            },
        )
        response.raise_for_status()


class MediaJanitor:
    """Xoá file Cloudinary ở luồng nền; lỗi chỉ ghi log, không làm hỏng việc đang làm."""

    def __init__(self, client: MediaDestroyer | None) -> None:
        self._client = client
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="media-janitor")

    def delete(self, items: list[Media]) -> None:
        if self._client is None or not items:
            return
        self._executor.submit(self._delete_all, self._client, list(items))

    @staticmethod
    def _delete_all(client: MediaDestroyer, items: list[Media]) -> None:
        for item in items:
            try:
                client.destroy(item.public_id, item.kind)
            except Exception:
                logger.warning("Không xoá được file Cloudinary %s", item.public_id, exc_info=True)

    def close(self) -> None:
        """Chờ các việc đang chạy xong (dùng khi tắt app và trong test)."""
        self._executor.shutdown(wait=True)

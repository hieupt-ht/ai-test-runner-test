"""Ảnh/video hướng dẫn hoặc bằng chứng, lưu ở Cloudinary hoặc Drive (Sheet chỉ giữ link)."""

import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

CLOUDINARY_PREFIX = "https://res.cloudinary.com/"
DRIVE_PREFIX = "https://drive.google.com/file/d/"
# Link Drive của app luôn có đúng dạng này, không thêm tham số nào khác
_DRIVE_LINK = re.compile(r"^https://drive\.google\.com/file/d/([A-Za-z0-9_-]+)/view$")
FOREIGN_MEDIA = "Link ảnh/video không thuộc kho lưu trữ của app"
NOT_CONFIGURED = "Chưa cấu hình Cloudinary"
NOT_CONFIGURED_DRIVE = "Chưa cấu hình Google Drive"

Provider = Literal["cloudinary", "drive"]


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class Media(BaseModel):
    kind: MediaKind
    url: str = Field(max_length=500)
    public_id: str = Field(max_length=300)  # Cloudinary: public_id; Drive: ID file
    note: str = Field(default="", max_length=200)

    @field_validator("url")
    @classmethod
    def _only_known_hosts(cls, url: str) -> str:
        if not url.startswith((CLOUDINARY_PREFIX, DRIVE_PREFIX)):
            raise ValueError(FOREIGN_MEDIA)
        return url


# Tối đa 5 ảnh/video cho mỗi bước và 5 cho cả case
MediaList = Annotated[list[Media], Field(max_length=5)]


class ForeignMediaError(ValueError):
    """Link không thuộc kho của app (hoặc app chưa cấu hình nơi lưu đó)."""


def provider_of(media: Media) -> Provider:
    """File nằm ở đâu, nhận ra từ link của nó."""
    return "drive" if media.url.startswith(DRIVE_PREFIX) else "cloudinary"


def _drive_id(media: Media) -> str | None:
    match = _DRIVE_LINK.match(media.url)
    return match.group(1) if match else None


def thumbnail_url(media: Media) -> str | None:
    """Link ảnh nhỏ của file Drive (video thì là khung hình đầu); Cloudinary thì không có."""
    file_id = _drive_id(media)
    if file_id is None:
        return None
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"


def display_url(media: Media) -> str:
    """Link để nhúng làm ảnh (thẻ img / Markdown). Video thì trả link gốc."""
    if media.kind == MediaKind.IMAGE:
        return thumbnail_url(media) or media.url
    return media.url


def ensure_own_media(items: Iterable[Media], cloud_name: str, drive_enabled: bool) -> None:
    """Báo lỗi nếu có link không nằm trong kho của app (đúng cloud, hoặc đúng dạng link Drive)."""
    for item in items:
        if provider_of(item) == "drive":
            if not drive_enabled:
                raise ForeignMediaError(NOT_CONFIGURED_DRIVE)
            if _drive_id(item) != item.public_id:
                raise ForeignMediaError(FOREIGN_MEDIA)
        else:
            if not cloud_name:
                raise ForeignMediaError(NOT_CONFIGURED)
            if not item.url.startswith(f"{CLOUDINARY_PREFIX}{cloud_name}/"):
                raise ForeignMediaError(FOREIGN_MEDIA)

"""Ảnh/video hướng dẫn hoặc bằng chứng, lưu trên Cloudinary (Sheet chỉ giữ link)."""

from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

CLOUDINARY_PREFIX = "https://res.cloudinary.com/"
FOREIGN_MEDIA = "Link ảnh/video không thuộc kho Cloudinary của app"
NOT_CONFIGURED = "Chưa cấu hình Cloudinary"


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class Media(BaseModel):
    kind: MediaKind
    url: str = Field(max_length=500)
    public_id: str = Field(max_length=300)
    note: str = Field(default="", max_length=200)

    @field_validator("url")
    @classmethod
    def _only_cloudinary_https(cls, url: str) -> str:
        if not url.startswith(CLOUDINARY_PREFIX):
            raise ValueError(FOREIGN_MEDIA)
        return url


# Tối đa 5 ảnh/video cho mỗi bước và 5 cho cả case
MediaList = Annotated[list[Media], Field(max_length=5)]


class ForeignMediaError(ValueError):
    """Link không thuộc kho Cloudinary của app (hoặc app chưa cấu hình Cloudinary)."""


def ensure_own_cloud(items: Iterable[Media], cloud_name: str) -> None:
    """Báo lỗi nếu có link không nằm trong đúng cloud của app."""
    items = list(items)
    if not items:
        return
    if not cloud_name:
        raise ForeignMediaError(NOT_CONFIGURED)
    own_prefix = f"{CLOUDINARY_PREFIX}{cloud_name}/"
    if any(not item.url.startswith(own_prefix) for item in items):
        raise ForeignMediaError(FOREIGN_MEDIA)

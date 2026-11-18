"""Phần dùng chung cho hai endpoint tải ảnh/video lên Google Drive (tester và agent)."""

from fastapi import HTTPException, UploadFile, status

from app.api.services import Services
from app.core.media.cloudinary import MAX_BYTES, Purpose
from app.core.media.drive import DriveError
from app.core.models.media import NOT_CONFIGURED_DRIVE, Media, MediaKind
from app.core.models.project import Project

ALLOWED_TYPES: dict[str, MediaKind] = {
    "image/jpeg": MediaKind.IMAGE,
    "image/png": MediaKind.IMAGE,
    "image/webp": MediaKind.IMAGE,
    "image/gif": MediaKind.IMAGE,
    "video/mp4": MediaKind.VIDEO,
    "video/quicktime": MediaKind.VIDEO,
    "video/webm": MediaKind.VIDEO,
}
ON_CLOUDINARY = "Dự án này lưu ảnh/video trên Cloudinary"
ON_DRIVE = "Dự án này lưu ảnh/video trên Google Drive"


def require_storage(project: Project, expected: str) -> None:
    """Chặn gọi nhầm luồng: dự án lưu ở nơi nào thì chỉ dùng luồng của nơi đó."""
    if project.storage != expected:
        message = ON_DRIVE if project.storage == "drive" else ON_CLOUDINARY
        raise HTTPException(status.HTTP_409_CONFLICT, message)


def _size_of(file: UploadFile) -> int:
    if file.size is not None:
        return file.size
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    return size


def kind_of_upload(content_type: str | None, size: int) -> MediaKind:
    """Loại và dung lượng hợp lệ thì trả loại; không thì 415/413 (trước khi gọi Drive)."""
    kind = ALLOWED_TYPES.get((content_type or "").lower())
    if kind is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Chỉ nhận ảnh hoặc video")
    if size > MAX_BYTES[kind]:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File quá lớn")
    return kind


def upload_to_drive(
    services: Services, project: Project, purpose: Purpose, file: UploadFile
) -> Media:
    require_storage(project, "drive")
    if services.drive is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_CONFIGURED_DRIVE)
    size = _size_of(file)
    kind = kind_of_upload(file.content_type, size)
    try:
        return services.drive.upload(
            project.id, purpose, kind, file.filename or "", file.content_type or "", file.file, size
        )
    except DriveError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from None

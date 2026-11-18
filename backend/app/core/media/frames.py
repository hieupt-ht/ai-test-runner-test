"""Ảnh cắt từ video: Cloudinary tự tạo khung hình theo giây, không cần tải video về."""

from app.core.models.media import Media, MediaKind

# Các giây cần lấy khung hình (video tối đa 3 phút, 6 ảnh là đủ để hình dung)
FRAME_SECONDS = (1, 3, 5, 7, 9, 11)
UPLOAD_SEGMENT = "/video/upload/"


def video_frame_urls(media: Media) -> list[str]:
    """Link ảnh .jpg ở các giây trong FRAME_SECONDS; không phải video thì trả danh sách rỗng."""
    if media.kind != MediaKind.VIDEO or UPLOAD_SEGMENT not in media.url:
        return []
    head, tail = media.url.split(UPLOAD_SEGMENT, 1)
    stem = tail.rsplit(".", 1)[0] if "." in tail.rsplit("/", 1)[-1] else tail
    return [f"{head}{UPLOAD_SEGMENT}so_{second}/{stem}.jpg" for second in FRAME_SECONDS]

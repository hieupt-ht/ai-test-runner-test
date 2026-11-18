"""Ảnh cắt từ video: Cloudinary tự tạo khung hình theo giây, không cần tải video về."""

from app.core.media.frames import FRAME_SECONDS, video_frame_urls
from app.core.models.media import Media

VIDEO_URL = "https://res.cloudinary.com/c/video/upload/v1/ai-test-runner/P/guide/x.mp4"


def test_video_frames() -> None:
    video = Media(kind="video", url=VIDEO_URL, public_id="x")
    urls = video_frame_urls(video)
    assert urls[0] == "https://res.cloudinary.com/c/video/upload/so_1/v1/ai-test-runner/P/guide/x.jpg"
    assert len(urls) == len(FRAME_SECONDS) == 6


def test_frame_seconds_follow_the_plan() -> None:
    assert FRAME_SECONDS == (1, 3, 5, 7, 9, 11)


def test_image_has_no_frames() -> None:
    image = Media(
        kind="image", url="https://res.cloudinary.com/c/image/upload/v1/a.png", public_id="a"
    )
    assert video_frame_urls(image) == []


def test_video_url_without_upload_segment_gives_no_frames() -> None:
    video = Media(kind="video", url="https://res.cloudinary.com/c/video/fetch/x.mp4", public_id="x")
    assert video_frame_urls(video) == []

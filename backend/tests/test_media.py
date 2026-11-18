import pytest
from pydantic import ValidationError

from app.core.models.media import (
    ForeignMediaError,
    Media,
    display_url,
    ensure_own_media,
    provider_of,
)

MINE = "https://res.cloudinary.com/mine/image/upload/a.png"


def make_media(url: str = MINE) -> Media:
    return Media(kind="image", url=url, public_id="a")


@pytest.mark.parametrize(
    "url", ["http://res.cloudinary.com/c/a.png", "https://evil.com/a.png"]
)
def test_media_rejects_non_cloudinary_and_http(url: str) -> None:
    with pytest.raises(ValidationError):
        make_media(url)


def test_ensure_own_media() -> None:
    ok = make_media()
    other = ok.model_copy(update={"url": "https://res.cloudinary.com/other/image/upload/a.png"})

    ensure_own_media([ok], "mine", False)
    with pytest.raises(ForeignMediaError, match="không thuộc kho lưu trữ"):
        ensure_own_media([other], "mine", False)
    with pytest.raises(ForeignMediaError, match="Chưa cấu hình Cloudinary"):
        ensure_own_media([ok], "", False)
    ensure_own_media([], "", False)  # không có media thì không cần cấu hình


def test_cloud_name_must_match_whole_segment() -> None:
    # "mine2" không được lọt qua khi kho của mình là "mine"
    tricky = make_media("https://res.cloudinary.com/mine2/image/upload/a.png")
    with pytest.raises(ForeignMediaError):
        ensure_own_media([tricky], "mine", False)


DRIVE = "https://drive.google.com/file/d/abc123/view"


def drive_media(kind: str = "image", url: str = DRIVE, public_id: str = "abc123") -> Media:
    return Media(kind=kind, url=url, public_id=public_id)


def test_media_accepts_cloudinary_and_drive_links() -> None:
    assert make_media().url == MINE
    assert drive_media().url == DRIVE


def test_provider_of() -> None:
    assert provider_of(make_media()) == "cloudinary"
    assert provider_of(drive_media()) == "drive"


def test_drive_requires_drive_enabled() -> None:
    ensure_own_media([drive_media()], "", True)  # Drive bật thì không cần cloud_name
    with pytest.raises(ForeignMediaError, match="Chưa cấu hình Google Drive"):
        ensure_own_media([drive_media()], "mine", False)


def test_drive_link_with_mismatched_id_is_rejected() -> None:
    forged = drive_media(public_id="khac")
    with pytest.raises(ForeignMediaError):
        ensure_own_media([forged], "", True)


def test_drive_link_must_be_exact_view_link() -> None:
    extra = drive_media(url="https://drive.google.com/file/d/abc123/view?usp=sharing")
    with pytest.raises(ForeignMediaError):
        ensure_own_media([extra], "", True)


def test_display_url_for_drive_image_is_thumbnail() -> None:
    assert display_url(drive_media()) == "https://drive.google.com/thumbnail?id=abc123&sz=w1600"


def test_display_url_keeps_cloudinary_and_drive_video_links() -> None:
    assert display_url(make_media()) == MINE
    assert display_url(drive_media("video")) == DRIVE

import pytest
from pydantic import ValidationError

from app.core.models.media import ForeignMediaError, Media, ensure_own_cloud

MINE = "https://res.cloudinary.com/mine/image/upload/a.png"


def make_media(url: str = MINE) -> Media:
    return Media(kind="image", url=url, public_id="a")


@pytest.mark.parametrize(
    "url", ["http://res.cloudinary.com/c/a.png", "https://evil.com/a.png"]
)
def test_media_rejects_non_cloudinary_and_http(url: str) -> None:
    with pytest.raises(ValidationError):
        make_media(url)


def test_ensure_own_cloud() -> None:
    ok = make_media()
    other = ok.model_copy(update={"url": "https://res.cloudinary.com/other/image/upload/a.png"})

    ensure_own_cloud([ok], "mine")
    with pytest.raises(ForeignMediaError, match="không thuộc kho Cloudinary"):
        ensure_own_cloud([other], "mine")
    with pytest.raises(ForeignMediaError, match="Chưa cấu hình Cloudinary"):
        ensure_own_cloud([ok], "")
    ensure_own_cloud([], "")  # không có media thì không cần cấu hình


def test_cloud_name_must_match_whole_segment() -> None:
    # "mine2" không được lọt qua khi kho của mình là "mine"
    tricky = make_media("https://res.cloudinary.com/mine2/image/upload/a.png")
    with pytest.raises(ForeignMediaError):
        ensure_own_cloud([tricky], "mine")

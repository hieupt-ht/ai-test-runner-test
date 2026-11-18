"""Drive chỉ bật khi đủ ba biến OAuth; thiếu một biến là tắt hẳn."""

from app.api.services import build_drive
from app.core.media.drive import DriveClient
from app.settings import Settings


def settings(**values: str) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_drive_is_off_when_oauth_is_incomplete() -> None:
    assert build_drive(settings()) is None
    partial = settings(google_oauth_client_id="id", google_oauth_client_secret="s")
    assert build_drive(partial) is None


def test_drive_is_on_when_oauth_is_complete() -> None:
    drive = build_drive(
        settings(
            google_oauth_client_id="id",
            google_oauth_client_secret="s",
            google_oauth_refresh_token="r",
        )
    )

    assert isinstance(drive, DriveClient)

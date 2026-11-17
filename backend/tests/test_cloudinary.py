"""Ký upload Cloudinary: đúng quy tắc chữ ký, không lộ secret, dọn file lỗi chỉ ghi log."""

import hashlib
import logging

import httpx
import pytest

from app.core.media.cloudinary import CloudinaryClient, CloudinarySigner, MediaJanitor
from app.core.models.media import Media, MediaKind


def make_signer() -> CloudinarySigner:
    return CloudinarySigner("c", "k", "s", now=lambda: 1700000000, token=lambda n: "abc")


def test_signature_matches_cloudinary_rule() -> None:
    signed = make_signer().sign("PRJ-0001", "guide", MediaKind.IMAGE)

    raw = (
        "allowed_formats=jpg,jpeg,png,webp,gif&folder=ai-test-runner/PRJ-0001/guide"
        "&public_id=abc&timestamp=1700000000s"
    )
    assert signed.signature == hashlib.sha1(raw.encode()).hexdigest()
    assert "s" not in signed.model_dump().values()  # không lộ secret
    assert signed.folder == "ai-test-runner/PRJ-0001/guide"
    assert signed.public_id == "abc"
    assert signed.resource_type == "image"
    assert signed.max_bytes == 10_485_760
    assert signed.upload_url == "https://api.cloudinary.com/v1_1/c/image/upload"


def test_video_limits_and_formats() -> None:
    signed = make_signer().sign("PRJ-0001", "evidence", MediaKind.VIDEO)

    assert signed.allowed_formats == "mp4,mov,webm"
    assert signed.max_bytes == 104_857_600
    assert signed.resource_type == "video"
    assert signed.folder == "ai-test-runner/PRJ-0001/evidence"
    assert signed.upload_url.endswith("/video/upload")


def test_public_id_is_random_by_default() -> None:
    signer = CloudinarySigner("c", "k", "s")
    first = signer.sign("PRJ-0001", "guide", MediaKind.IMAGE)
    second = signer.sign("PRJ-0001", "guide", MediaKind.IMAGE)
    assert first.public_id != second.public_id


def test_destroy_posts_signed_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"result": "ok"})

    client = CloudinaryClient(
        "c",
        "k",
        "s",
        now=lambda: 1700000000,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.destroy("ai-test-runner/PRJ-0001/guide/abc", MediaKind.VIDEO)

    request = seen[0]
    assert str(request.url) == "https://api.cloudinary.com/v1_1/c/video/destroy"
    body = request.content.decode()
    raw = "public_id=ai-test-runner/PRJ-0001/guide/abc&timestamp=1700000000s"
    assert hashlib.sha1(raw.encode()).hexdigest() in body
    assert "api_key=k" in body
    assert "api_secret" not in body


class BrokenClient:
    def destroy(self, public_id: str, kind: MediaKind) -> None:
        raise RuntimeError("Cloudinary sập")


class RecordingClient:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def destroy(self, public_id: str, kind: MediaKind) -> None:
        self.deleted.append(public_id)


def media(public_id: str) -> Media:
    return Media(
        kind=MediaKind.IMAGE,
        url="https://res.cloudinary.com/c/image/upload/x.png",
        public_id=public_id,
    )


def test_janitor_logs_and_swallows_errors(caplog: pytest.LogCaptureFixture) -> None:
    janitor = MediaJanitor(BrokenClient())
    with caplog.at_level(logging.WARNING):
        janitor.delete([media("a")])
        janitor.close()  # chờ luồng nền chạy xong

    assert "Không xoá được" in caplog.text


def test_janitor_deletes_each_item_in_background() -> None:
    client = RecordingClient()
    janitor = MediaJanitor(client)
    janitor.delete([media("a"), media("b")])
    janitor.close()
    assert client.deleted == ["a", "b"]


def test_janitor_without_client_does_nothing() -> None:
    janitor = MediaJanitor(None)
    janitor.delete([media("a")])
    janitor.close()

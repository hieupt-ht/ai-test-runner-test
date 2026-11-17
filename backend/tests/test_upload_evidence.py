"""Script cho Codex: xin chữ ký rồi đẩy file bằng chứng lên Cloudinary."""

import json
from pathlib import Path

import httpx
import pytest

from app.tools.upload_evidence import UploadError, main, upload

SIGN = {
    "cloud_name": "demo",
    "api_key": "key1",
    "timestamp": 1700000000,
    "signature": "sig",
    "folder": "ai-test-runner/PRJ-0001/evidence",
    "public_id": "abc",
    "allowed_formats": "jpg,jpeg,png,webp,gif",
    "resource_type": "image",
    "max_bytes": 10485760,
    "upload_url": "https://api.cloudinary.com/v1_1/demo/image/upload",
}


def make_http(seen: list[httpx.Request], sign_status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/media/sign"):
            return httpx.Response(sign_status, json=SIGN if sign_status == 200 else {"detail": "x"})
        return httpx.Response(
            200,
            json={
                "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/x/abc.png",
                "public_id": "ai-test-runner/PRJ-0001/evidence/abc",
                "resource_type": "image",
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def shot(tmp_path: Path) -> Path:
    path = tmp_path / "shot.png"
    path.write_bytes(b"\x89PNG")
    return path


def test_upload_signs_then_posts_file_and_returns_media(shot: Path) -> None:
    seen: list[httpx.Request] = []
    media = upload(
        shot, project_id="PRJ-0001", note="Bước 2", base_url="http://app/", token="t",
        http=make_http(seen),
    )
    sign, post = seen
    assert sign.url.path == "/api/agent/projects/PRJ-0001/media/sign"
    assert sign.headers["Authorization"] == "Bearer t"
    assert json.loads(sign.content) == {"kind": "image"}
    assert str(post.url) == SIGN["upload_url"]
    assert b"sig" in post.content and b"shot.png" in post.content
    assert media == {
        "kind": "image",
        "url": "https://res.cloudinary.com/demo/image/upload/v1/x/abc.png",
        "public_id": "ai-test-runner/PRJ-0001/evidence/abc",
        "note": "Bước 2",
    }


def test_video_extension_means_video_kind(tmp_path: Path) -> None:
    clip = tmp_path / "run.mp4"
    clip.write_bytes(b"x")
    seen: list[httpx.Request] = []
    upload(clip, project_id="P", note="", base_url="http://app", token="t", http=make_http(seen))
    assert json.loads(seen[0].content) == {"kind": "video"}


def test_unauthorized_error_never_contains_token(shot: Path) -> None:
    with pytest.raises(UploadError) as error:
        upload(
            shot, project_id="P", note="", base_url="http://app", token="SECRET-TOKEN",
            http=make_http([], sign_status=401),
        )
    assert "SECRET-TOKEN" not in str(error.value)
    assert "401" in str(error.value)


def test_missing_env_exits_with_code_2_and_vietnamese_message(
    shot: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    monkeypatch.delenv("AI_TEST_RUNNER_URL", raising=False)
    assert main(["--project", "P", "--file", str(shot)]) == 2
    assert "AGENT_API_TOKEN" in capsys.readouterr().err


def test_main_prints_one_json_line(
    shot: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENT_API_TOKEN", "t")
    monkeypatch.setenv("AI_TEST_RUNNER_URL", "http://app")
    code = main(["--project", "P", "--file", str(shot)], http=make_http([]))
    out = capsys.readouterr().out
    assert code == 0
    assert json.loads(out)["kind"] == "image" and out.count("\n") == 1

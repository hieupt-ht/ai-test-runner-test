"""Script cho Codex: đẩy một ảnh/video bằng chứng lên Cloudinary rồi in `Media` dạng JSON.

Cách dùng (từ thư mục backend):
    uv run python -m app.tools.upload_evidence --project PRJ-0001 --file shot.png --note "Bước 2"

Cần hai biến môi trường: AGENT_API_TOKEN và AI_TEST_RUNNER_URL (địa chỉ app).
Token không bao giờ được in ra, kể cả khi lỗi.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}


class UploadError(Exception):
    """Lỗi upload, nội dung đã được viết sẵn bằng tiếng Việt và không chứa token."""


def guess_kind(path: Path) -> str:
    return "video" if path.suffix.lower() in VIDEO_SUFFIXES else "image"


def upload(
    path: Path, *, project_id: str, note: str, base_url: str, token: str, http: httpx.Client
) -> dict[str, str]:
    """Xin chữ ký ở app rồi đẩy file thẳng lên Cloudinary; trả về dict `Media`."""
    kind = guess_kind(path)
    sign_url = f"{base_url.rstrip('/')}/api/agent/projects/{project_id}/media/sign"
    try:
        signed = http.post(
            sign_url, json={"kind": kind}, headers={"Authorization": f"Bearer {token}"}
        )
    except httpx.HTTPError:
        raise UploadError("Không kết nối được tới app để xin chữ ký upload") from None
    if signed.status_code != 200:
        raise UploadError(f"App từ chối cấp chữ ký upload (mã {signed.status_code})")
    sign = signed.json()

    fields = {
        "api_key": sign["api_key"],
        "timestamp": str(sign["timestamp"]),
        "signature": sign["signature"],
        "folder": sign["folder"],
        "public_id": sign["public_id"],
        "allowed_formats": sign["allowed_formats"],
    }
    try:
        with path.open("rb") as handle:
            sent = http.post(sign["upload_url"], data=fields, files={"file": (path.name, handle)})
    except (httpx.HTTPError, OSError):
        raise UploadError("Không đẩy được file lên Cloudinary") from None
    if sent.status_code != 200:
        raise UploadError(f"Cloudinary từ chối file (mã {sent.status_code})")
    body = sent.json()
    return {
        "kind": kind,
        "url": body["secure_url"],
        "public_id": body["public_id"],
        "note": note,
    }


def main(argv: list[str] | None = None, *, http: httpx.Client | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload bằng chứng lên Cloudinary")
    parser.add_argument("--project", required=True, help="Mã dự án, ví dụ PRJ-0001")
    parser.add_argument("--file", required=True, type=Path, help="Đường dẫn ảnh/video")
    parser.add_argument("--note", default="", help="Ghi chú ngắn, ví dụ 'Bước 2'")
    args = parser.parse_args(argv)

    token = os.environ.get("AGENT_API_TOKEN", "")
    base_url = os.environ.get("AI_TEST_RUNNER_URL", "")
    if not token or not base_url:
        print("Thiếu biến môi trường AGENT_API_TOKEN hoặc AI_TEST_RUNNER_URL", file=sys.stderr)
        return 2
    if not args.file.is_file():
        print(f"Không tìm thấy file: {args.file}", file=sys.stderr)
        return 2

    client = http or httpx.Client(timeout=120)
    try:
        media = upload(
            args.file, project_id=args.project, note=args.note,
            base_url=base_url, token=token, http=client,
        )
    except UploadError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(media, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

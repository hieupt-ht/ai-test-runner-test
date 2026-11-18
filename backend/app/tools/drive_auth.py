"""Script lấy refresh token Google Drive (chạy một lần trên máy của chủ dự án).

Cách dùng (từ thư mục backend, đã điền GOOGLE_OAUTH_CLIENT_ID/SECRET trong .env):
    uv run python -m app.tools.drive_auth

Script mở trình duyệt để bạn đăng nhập Gmail và cấp quyền, rồi in đúng một dòng
`GOOGLE_OAUTH_REFRESH_TOKEN=...` để bạn tự dán vào `.env`. Script không ghi file nào.
Nhớ đăng ký `http://localhost:8765` là "Authorized redirect URI" của OAuth client.
"""

import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from app.settings import Settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.file"  # chỉ thấy file do app tạo
PORT = 8765
REDIRECT_URI = f"http://localhost:{PORT}"


class AuthError(Exception):
    """Lỗi lấy token, nội dung tiếng Việt và không chứa client secret."""


def build_auth_url(client_id: str, redirect_uri: str) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",  # để Google trả refresh token
            "prompt": "consent",  # ép hỏi lại để chắc chắn có refresh token
        }
    )
    return f"{AUTH_URL}?{query}"


def exchange_code(
    code: str, client_id: str, client_secret: str, redirect_uri: str, http: httpx.Client
) -> str:
    """Đổi mã Google vừa trả về lấy refresh token."""
    try:
        response = http.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    except httpx.HTTPError:
        raise AuthError("Không kết nối được tới Google") from None
    if response.status_code != 200:
        raise AuthError(f"Google từ chối mã đăng nhập (mã {response.status_code}), thử chạy lại")
    refresh_token = response.json().get("refresh_token")
    if not refresh_token:
        raise AuthError(
            "Google không trả refresh token. Vào myaccount.google.com/permissions, "
            "gỡ quyền của app này rồi chạy lại script"
        )
    return str(refresh_token)


def _wait_for_code() -> str:
    """Mở máy chủ tạm ở localhost, chờ Google chuyển trình duyệt về kèm `code`."""
    found: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            found.update({k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Xong! Bạn có thể đóng tab này.".encode())

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # không in log (URL có chứa mã đăng nhập)

    with HTTPServer(("localhost", PORT), Handler) as server:
        server.handle_request()
    if "code" not in found:
        raise AuthError("Bạn chưa cấp quyền hoặc đã huỷ")
    return found["code"]


def main(*, env_file: str | None = ".env") -> int:
    settings = Settings(_env_file=env_file)
    client_id, client_secret = settings.google_oauth_client_id, settings.google_oauth_client_secret
    if not client_id or not client_secret:
        print("Thiếu GOOGLE_OAUTH_CLIENT_ID hoặc _SECRET trong .env", file=sys.stderr)
        return 2
    print("Đang mở trình duyệt để bạn cấp quyền Google Drive...", file=sys.stderr)
    webbrowser.open(build_auth_url(client_id, REDIRECT_URI))
    try:
        code = _wait_for_code()
        with httpx.Client(timeout=30) as http:
            token = exchange_code(code, client_id, client_secret, REDIRECT_URI, http)
    except AuthError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

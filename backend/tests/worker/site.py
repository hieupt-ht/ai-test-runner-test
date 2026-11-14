"""Một trang web nhỏ do test tự dựng, để chạy thử Playwright mà không cần app thật.

- /login : ô "Email", ô "Mật khẩu", nút "Đăng nhập" (đặt cookie rồi chuyển sang /home)
- /home  : hiện "Xin chào" nếu đã đăng nhập, chưa thì quay lại /login
- /form  : ô "Họ tên", danh sách "Thành phố", nút "Gửi" làm hiện chữ "Đã gửi"
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

PAGES = {
    "/login": """
<h1>Trang đăng nhập</h1>
<label>Email <input id="email" type="text"></label>
<label>Mật khẩu <input id="password" type="password"></label>
<button onclick="document.cookie='session=1; path=/'; location.href='/home'">Đăng nhập</button>
""",
    "/home": """
<p id="greeting"></p>
<script>
  if (document.cookie.includes('session=1')) {
    document.getElementById('greeting').textContent = 'Xin chào';
  } else {
    location.href = '/login';
  }
</script>
""",
    "/form": """
<h1>Biểu mẫu</h1>
<label>Họ tên <input id="name" type="text"></label>
<label>Thành phố
  <select id="city">
    <option value="hn">Hà Nội</option>
    <option value="dn">Đà Nẵng</option>
  </select>
</label>
<button id="send" onclick="document.getElementById('done').hidden = false">Gửi</button>
<p id="done" hidden>Đã gửi</p>
""",
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = PAGES.get(self.path.split("?")[0])
        if body is None:
            self.send_error(404)
            return
        html = f'<!doctype html><html><head><meta charset="utf-8"></head><body>{body}</body></html>'
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass  # im lặng


@contextmanager
def serve() -> Iterator[str]:
    """Chạy server ở một cổng trống, trả về địa chỉ gốc, ví dụ http://127.0.0.1:54321."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    # Chạy như một "app" thật để thử RunExecutor từ đầu đến cuối: python site.py <cổng>
    import sys

    HTTPServer(("127.0.0.1", int(sys.argv[1])), _Handler).serve_forever()

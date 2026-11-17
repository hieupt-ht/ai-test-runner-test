# Thiết kế: Đăng nhập bằng email + mật khẩu (thay Google OAuth)

Ngày: 2026-11-17. Trạng thái: **chờ chủ dự án duyệt**.

## 1. Mục đích

Sếp chưa cần đăng nhập Google. Công ty chỉ cần Admin tạo tài khoản bằng email công ty và cấp sẵn mật khẩu; thành viên dùng email + mật khẩu đó để vào app. Dữ liệu vẫn nằm trong Google Sheets, backend vẫn đọc/ghi bằng Service Account.

## 2. Mục tiêu / Không phải mục tiêu / Điều phải tránh

**Mục tiêu**
- Đăng nhập bằng email + mật khẩu riêng của app.
- Admin đầu tiên tạo từ `.env`; Admin tạo user và đặt/đặt lại mật khẩu.
- Mọi người tự đổi được mật khẩu của mình.
- Gỡ hẳn Google OAuth (authlib, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).

**Không phải mục tiêu**
- Không nối vào hệ thống mail công ty (IMAP/LDAP/SSO); app không bao giờ thấy mật khẩu mail thật.
- Không bắt buộc đổi mật khẩu ở lần đăng nhập đầu (đã chốt).
- Không quên mật khẩu qua email (Admin đặt lại thủ công).
- Không đổi Service Account, Sheets, phân quyền theo vai trò, session Redis.

**Điều phải tránh**
- Lưu mật khẩu thật (chỉ lưu bản băm); để lộ mật khẩu hay hash qua API, log, hay Sheet công khai.
- Lộ email nào tồn tại trong hệ thống qua thông báo lỗi.

## 3. Hiện trạng

- Đăng nhập: `backend/app/api/routers/auth.py` (`/api/auth/login`, `/api/auth/callback`) dùng `services.oauth`; `core/services/auth.py::authenticate` chỉ kiểm tra email có trong tab `Users` và `active`.
- Phiên (session) trong Redis + cookie `httponly` giữ nguyên.
- `core/bootstrap.py` tạo Admin đầu tiên từ `BOOTSTRAP_ADMIN_EMAIL` khi tab `Users` trống.
- API quản lý user: `POST /api/users`, `PATCH /api/users/{email}`.
- Tab `Users`: `email, name, role, active, created_at` — chưa có cột mật khẩu.

## 4. Các cách làm đã cân nhắc

| Cách | Đánh đổi | Kết quả |
|------|----------|---------|
| **A. Mật khẩu riêng của app, Admin cấp** | Đơn giản, an toàn, app tự giữ hash | **Được chọn** |
| B. Dùng lại mật khẩu mail công ty (IMAP/LDAP/SSO) | Phụ thuộc hệ thống mail, mong manh, app xử lý mật khẩu mail thật | Loại |
| C. Giữ Google OAuth làm lựa chọn phụ | Giữ nguyên phần cấu hình Google Cloud mà sếp không muốn | Loại (đã chốt: gỡ hẳn) |

Sheet cũng cân nhắc để công khai hoặc dùng Apps Script thay Service Account: **loại**, vì API Google không cho ghi nếu chỉ có API key, và công khai làm lộ `test_data`/email. Giữ Service Account, Sheet để riêng tư.

## 5. Thiết kế

**Dữ liệu.** Thêm cột `password_hash` vào cuối tab `Users` (bootstrap đã tự thêm cột thiếu). Model `User` trả ra API **không** có trường này; repository dùng một model/đường riêng cho hash.

**Băm.** `argon2` (thư viện `argon2-cffi`). Mật khẩu tối thiểu 8 ký tự.

**Admin đầu tiên.** `.env` có `BOOTSTRAP_ADMIN_EMAIL` và `BOOTSTRAP_ADMIN_PASSWORD`. Khi tab `Users` trống thì tạo Admin kèm hash. Nếu Admin đã tồn tại mà chưa có hash (đã chạy bản cũ) và có `BOOTSTRAP_ADMIN_PASSWORD` thì đặt hash cho Admin bootstrap đó (chỉ khi hash đang trống). Thiếu mật khẩu khi cần tạo Admin → báo `ConfigError` rõ ràng.

**API (backend)**
- `POST /api/auth/login` `{email, password}` → tạo session + cookie; sai thì `401 {"detail": "Email hoặc mật khẩu không đúng"}` (cùng một câu cho mọi lý do: sai email, sai mật khẩu, user bị khoá, chưa có mật khẩu).
- `POST /api/auth/logout`, `GET /api/me`: giữ nguyên.
- `POST /api/auth/change-password` `{current_password, new_password}` (người đang đăng nhập).
- `POST /api/users` nhận thêm `password` (bắt buộc); `POST /api/users/{email}/reset-password` `{password}` (chỉ Admin).
- Đổi/đặt lại mật khẩu → xoá mọi session của người đó.
- Bỏ `/api/auth/callback`, `/api/auth/login` kiểu redirect, `services.oauth`, `api/oauth.py`.

**Chống dò mật khẩu.** Đếm lần sai theo email trong Redis; sai 5 lần → khoá 15 phút (trả `429` với câu tiếng Việt). Đăng nhập đúng thì xoá bộ đếm. Lỗi khoá không tiết lộ email có tồn tại.

**Frontend.** Trang `/login`: form email + mật khẩu (bỏ nút Google và các mã lỗi `oauth_failed`, `not_allowed`). Form tạo user thêm ô mật khẩu tạm; có nút "Đặt lại mật khẩu" cho Admin; có mục "Đổi mật khẩu" cho mọi người. Chuỗi giao diện ở `frontend/messages/vi.json`; chạy `npm run gen:api` sau khi sửa API.

**Tài liệu.** Cập nhật `SETUP.md` (bỏ bước 1.3, 1.4, biến Google OAuth; thêm `BOOTSTRAP_ADMIN_PASSWORD`), `README.md`, `docs/architecture.md`, `HANDOFF.md`, `.env.example`.

## 6. Việc để builder tự quyết (đã đánh dấu là lựa chọn của thiết kế)

- Số lần sai (5) và thời gian khoá (15 phút) đặt thành hằng số dễ chỉnh.
- Tên chính xác của model/đường lưu hash, miễn không lộ ra API.
- Cách chuyển Admin đã có sẵn trong Sheet (xem phần "Admin đầu tiên").

## 7. Kiểm thử

TDD, test trước. Phủ: hash/verify; đăng nhập đúng/sai/user khoá/chưa có mật khẩu (cùng thông báo); khoá sau 5 lần sai và mở lại; đổi/đặt lại mật khẩu xoá session; hash không xuất hiện trong response nào; bootstrap Admin có mật khẩu; frontend form đăng nhập, tạo user, đặt lại, đổi mật khẩu. Chạy đủ `pytest`, `mypy`, `ruff`, `vitest`, `typecheck`, `lint` trước khi báo xong.

## 8. Cách chia đợt (gợi ý cho kế hoạch)

1. Backend: hash, cột `password_hash`, bootstrap, login/logout, chống dò.
2. Backend: đổi/đặt lại mật khẩu, tạo user có mật khẩu, gỡ OAuth.
3. Frontend: trang đăng nhập, form tạo user, đặt lại, đổi mật khẩu.
4. Tài liệu và dọn cấu hình.

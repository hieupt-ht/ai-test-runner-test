# Đăng nhập bằng email + mật khẩu — Kế hoạch thực hiện

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay đăng nhập Google OAuth bằng email + mật khẩu riêng của app (Admin cấp), giữ nguyên Service Account và Sheet riêng tư.

**Architecture:** Cột `password_hash` (argon2) nằm ở cuối tab `Users`, không nằm trong model `User` nên không lọt ra API. `UserRepository` có thêm đường riêng để ghi/đọc hash. Đăng nhập kiểm tra bộ đếm chống dò trong Redis, rồi xác minh hash, rồi tạo session như cũ. Đổi/đặt lại mật khẩu xoá mọi session của người đó.

**Tech Stack:** FastAPI, `argon2-cffi`, Redis, Google Sheets (gateway), Next.js 16 + next-intl.

**Spec:** `docs/superpowers/specs/2026-11-17-password-login-design.md`

## Global Constraints

- Mật khẩu tối thiểu **8 ký tự** (tối đa 128, để không bị gửi chuỗi khổng lồ băm tốn CPU).
- Câu lỗi đăng nhập sai (mọi lý do: sai email, sai mật khẩu, user khoá, chưa có mật khẩu): `401 {"detail": "Email hoặc mật khẩu không đúng"}`.
- Khoá: sai **5** lần theo email thì khoá **15 phút**, trả `429` với câu tiếng Việt; hằng số `MAX_FAILED_LOGINS = 5`, `LOCK_SECONDS = 15 * 60`. Đăng nhập đúng xoá bộ đếm.
- Không bao giờ để `password_hash` hay mật khẩu xuất hiện trong response, log, audit log (`diff`) hay thông báo.
- Chỉ `gateway.py` gọi Google; chỉ backend ghi Sheet qua repository. Lỗi API có `{"detail": "<tiếng Việt>"}`. Chuỗi giao diện ở `frontend/messages/vi.json`.
- TDD: test đỏ trước, rồi mới code. Comment tiếng Việt đơn giản. Commit Conventional Commits (type tiếng Anh, nội dung tiếng Việt có dấu, heredoc Git Bash), trên nhánh `feature/ai-agent-runner`. Không push, không tạo PR.
- Không đọc, in hay commit giá trị trong `.env`. Biến mới: `BOOTSTRAP_ADMIN_PASSWORD` (cùng `BOOTSTRAP_ADMIN_EMAIL` đã có).
- Làm từng đợt; xong đợt thì tick `[x]` ở đây, ghi tiến độ vào `HANDOFF.md`, dừng cho chủ dự án `/compact`.
- Kiểm tra cuối mỗi đợt: backend `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check`; frontend `cd frontend && npx vitest run && npm run typecheck && npm run lint`.

## Review Focus

1. Email viết hoa/có khoảng trắng khi đăng nhập (`"  An@X.com"`) vẫn khớp; bộ đếm khoá cũng chuẩn hoá email (không né khoá bằng cách đổi hoa/thường) — Task 3.
2. Email không tồn tại cũng bị đếm và khoá như email thật, và câu trả lời 401/429 giống nhau — không lộ email nào có trong hệ thống — Task 3.
3. Mật khẩu rỗng, quá ngắn (<8) hoặc quá dài (>128) khi tạo user / đổi / đặt lại → `422`, không ghi gì — Task 5, 6.
4. Ký tự tiếng Việt, khoảng trắng đầu/cuối và ký tự đặc biệt trong mật khẩu giữ nguyên (không `strip`) — Task 1.
5. Admin tự đặt lại mật khẩu của chính mình, hoặc user đang khoá/`active=false` được đặt lại: session cũ bị xoá, user khoá vẫn không đăng nhập được — Task 6.

---

## ĐỢT 1 — Backend: hash, cột, bootstrap, đăng nhập, chống dò

### Task 1: Băm và kiểm tra mật khẩu

**Files:**
- Create: `backend/app/core/passwords.py`
- Test: `backend/tests/test_passwords.py`
- Modify: `backend/pyproject.toml` (chạy `cd backend && uv add argon2-cffi`)

**Interfaces:**
- Produces: `MIN_PASSWORD_LENGTH = 8`, `MAX_PASSWORD_LENGTH = 128`; `hash_password(password: str) -> str`; `verify_password(password: str, password_hash: str) -> bool` (hash rỗng/sai định dạng → `False`, không ném lỗi).

- [ ] **Step 1: Viết test đỏ** trong `test_passwords.py`: `test_hash_is_not_plain_text` (hash khác mật khẩu và bắt đầu bằng `$argon2`), `test_verify_correct_password`, `test_verify_wrong_password_false`, `test_verify_empty_or_garbage_hash_false` (`""` và `"abc"` → `False`), `test_password_is_not_stripped` (`hash_password(" Mật khẩu ")` chỉ khớp đúng chuỗi có khoảng trắng), `test_two_hashes_of_same_password_differ`.
- [ ] **Step 2: Chạy** `uv run pytest tests/test_passwords.py -q` → FAIL (chưa có module).
- [ ] **Step 3: Implement** `passwords.py` bằng `argon2.PasswordHasher`; bắt `argon2.exceptions.VerificationError`/`InvalidHashError` trong `verify_password`. Test chạy nhanh: thêm fixture autouse trong `conftest.py` hạ chi phí hasher (monkeypatch `app.core.passwords._hasher` bằng `PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)`).
- [ ] **Step 4: Chạy lại** → PASS.
- [ ] **Step 5: Commit** `feat(auth): băm và kiểm tra mật khẩu bằng argon2`.

### Task 2: Cột `password_hash` và đường ghi/đọc hash trong repository

**Files:**
- Modify: `backend/app/core/sheets/schema.py:8` (thêm `"password_hash"` vào cuối `USER_COLUMNS`), `backend/app/core/repositories/users.py`
- Test: `backend/tests/test_user_repository.py`

**Interfaces:**
- Consumes: `User` (không đổi, không có hash).
- Produces trong `UserRepository`:
  - `create(self, user: User, password_hash: str = "") -> User`
  - `get_password_hash(self, email: str) -> str` (không có user/chưa có hash → `""`; đọc thẳng Sheet, không qua cache)
  - `set_password_hash(self, email: str, password_hash: str) -> None` (trong khoá `TAB_LOCK_KEY`; không có user → `UserNotFoundError`)
- Ràng buộc: `update(user)` **giữ nguyên** hash đang có (đọc lại hash ngay trong khoá rồi ghi cùng dòng); `_to_record` nhận thêm tham số hash; `_from_record` bỏ qua cột này; JSON cache `cache:users` không chứa hash.

- [ ] **Step 1: Viết test đỏ:** `test_create_stores_hash_in_sheet_not_in_user` (`users.create(make_user(..), password_hash="H")` → `get_password_hash("AN@x.com ")=="H"`, và `users.get(..).model_dump()` không có khoá `password_hash`), `test_update_keeps_existing_hash`, `test_set_password_hash_changes_only_hash`, `test_set_password_hash_unknown_user_raises`, `test_get_password_hash_missing_returns_empty`, `test_hash_not_in_redis_cache` (sau `list_all()`, `redis.get("cache:users")` không chứa `"H"`), `test_old_sheet_without_hash_column_still_reads` (Sheet Users chỉ có 5 cột cũ vẫn đọc được user).
- [ ] **Step 2: Chạy** `uv run pytest tests/test_user_repository.py -q` → FAIL.
- [ ] **Step 3: Implement** như Interfaces. Kiểm tra `SheetTable.read_all` trả `Record` có khoá `password_hash` rỗng khi ô trống (dùng `record.get("password_hash", "")`).
- [ ] **Step 4: Chạy** toàn bộ `uv run pytest -q` → PASS (một số test Sheet đếm cột có thể cần cập nhật theo `USER_COLUMNS` mới).
- [ ] **Step 5: Commit** `feat(users): thêm cột password_hash vào tab Users`.

### Task 3: Dịch vụ đăng nhập + chống dò mật khẩu

**Files:**
- Create: `backend/app/core/login_throttle.py`
- Modify: `backend/app/core/services/auth.py`
- Test: `backend/tests/test_login_throttle.py`, `backend/tests/test_auth_service.py`

**Interfaces:**
- Consumes: `hash/verify_password` (Task 1), `UserRepository.get_password_hash` (Task 2).
- Produces:
  - `LoginThrottle(redis: Redis, *, max_failures: int = MAX_FAILED_LOGINS, lock_seconds: int = LOCK_SECONDS)` với `is_locked(email: str) -> bool`, `record_failure(email: str) -> None`, `reset(email: str) -> None`. Khoá Redis `login_fail:{email chuẩn hoá}`; đếm bằng `INCR` + `EXPIRE lock_seconds`; `is_locked` khi đếm `>= max_failures`.
  - `class LoginLockedError(Exception)`.
  - `authenticate(users: UserRepository, email: str, password: str, throttle: LoginThrottle) -> User | None` — khoá thì ném `LoginLockedError`; sai thì `record_failure` rồi trả `None`; đúng thì `reset` rồi trả `User`. Luôn chạy một lần `verify_password` kể cả khi không có user (so với hash giả) để thời gian không lộ email tồn tại.

- [ ] **Step 1: Viết test đỏ** (`test_login_throttle.py`): `test_locks_after_five_failures`, `test_not_locked_at_four`, `test_reset_clears_counter`, `test_email_is_normalized` (`"A@x.com"` và `" a@X.com "` dùng chung bộ đếm), `test_lock_expires` (đếm có TTL ≈ `lock_seconds`). (`test_auth_service.py`): `test_correct_password_returns_user`, `test_wrong_password_returns_none_and_counts`, `test_unknown_email_returns_none_and_counts`, `test_inactive_user_returns_none`, `test_user_without_password_returns_none`, `test_locked_raises_even_with_correct_password`, `test_success_resets_counter`.
- [ ] **Step 2: Chạy** hai file test → FAIL.
- [ ] **Step 3: Implement** như Interfaces. Xoá test/ code `authenticate(users, email)` cũ nếu còn dùng (chỉ router cũ dùng).
- [ ] **Step 4: Chạy** hai file test → PASS.
- [ ] **Step 5: Commit** `feat(auth): kiểm tra mật khẩu và khoá sau 5 lần sai`.

### Task 4: Endpoint `POST /api/auth/login`, bootstrap Admin có mật khẩu

**Files:**
- Modify: `backend/app/api/routers/auth.py`, `backend/app/api/services.py` (thêm `login_throttle: LoginThrottle`), `backend/app/settings.py` (thêm `bootstrap_admin_password: str = ""`), `backend/app/core/bootstrap.py`, `backend/app/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_auth.py` (viết lại), `backend/tests/test_bootstrap.py`

**Interfaces:**
- Consumes: Task 1–3.
- Produces:
  - `POST /api/auth/login` body `LoginRequest(email: str, password: str)` → `200` trả `User`, đặt cookie `atr_session` (`httponly`, `samesite=lax`, `secure` khi `app_base_url` bắt đầu `https`); sai → `401` câu chung; khoá → `429 {"detail": "Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút"}`. Việc đọc Sheet chạy trong `run_in_threadpool`.
  - `bootstrap_system_spreadsheet(gateway, spreadsheet_id, users, bootstrap_admin_email: str, bootstrap_admin_password: str = "") -> list[str]`: Users trống + có email → thiếu mật khẩu thì `ConfigError("Thiếu BOOTSTRAP_ADMIN_PASSWORD trong .env")`, ngược lại tạo Admin kèm hash; Users không trống và Admin bootstrap tồn tại nhưng hash trống + có mật khẩu → `set_password_hash` (chỉ khi hash đang trống; hash đã có thì không đụng).
  - conftest: `log_in_as(client, users, email, role, password="mat-khau-test")` tạo user (nếu chưa có) với hash thật rồi gọi `POST /api/auth/login`; bỏ tham số `oauth` ở `log_in_as`, `client_for` và các fixture `client_as_*`.
  - `main.start_real_services` truyền `settings.bootstrap_admin_password`.

- [ ] **Step 1: Viết test đỏ** trong `test_auth.py`: `test_login_success_sets_cookie` (có `HttpOnly`, `samesite=lax`), `test_login_normalizes_email`, `test_login_wrong_password_401_generic`, `test_login_unknown_email_same_response_as_wrong_password` (so sánh body + status), `test_login_inactive_user_401_generic`, `test_login_user_without_password_401_generic`, `test_login_locked_after_5_failures_429`, `test_login_success_resets_counter`, `test_me_returns_user_without_hash`, `test_logout_deletes_session`, `test_user_deactivated_after_login_gets_401_next_request`, `test_old_oauth_routes_are_gone` (`GET /api/auth/callback` → 404). Trong `test_bootstrap.py`: `test_adds_bootstrap_admin_with_password` (đăng nhập được bằng `verify_password`), `test_missing_password_raises_config_error`, `test_existing_admin_without_hash_gets_hash`, `test_existing_hash_not_overwritten`, và sửa các test cũ truyền mật khẩu.
- [ ] **Step 2: Chạy** `uv run pytest tests/test_auth.py tests/test_bootstrap.py -q` → FAIL.
- [ ] **Step 3: Implement** như Interfaces. Router auth chỉ còn `login`, `logout`, `me`. (Đợt này **chưa** gỡ `oauth` khỏi `Services`/conftest nếu việc đó làm vỡ hàng loạt test; việc gỡ nằm ở Task 7. Nhưng `log_in_as` đã đổi sang login mật khẩu nên các test khác chạy được.) Khi sửa chữ ký `log_in_as`/`client_for`, cập nhật mọi nơi gọi (dùng Grep `log_in_as|client_for` trong `backend/tests`).
- [ ] **Step 4: Chạy** toàn bộ `uv run pytest -q && uv run mypy app && uv run ruff check` → sạch.
- [ ] **Step 5: Commit** `feat(auth): đăng nhập bằng email và mật khẩu, tạo Admin đầu tiên có mật khẩu`.

- [x] **Cuối đợt 1 (xong 2026-11-17, backend 578 test qua):** tick các task, ghi tiến độ vào `HANDOFF.md`, dừng cho `/compact`.

---

## ĐỢT 2 — Backend: đổi/đặt lại mật khẩu, tạo user có mật khẩu, gỡ OAuth

### Task 5: Tạo user kèm mật khẩu

**Files:**
- Modify: `backend/app/api/routers/users.py`, `backend/app/core/services/users.py`
- Test: `backend/tests/test_users_api.py`

**Interfaces:**
- Consumes: `UserRepository.create(user, password_hash)`, `hash_password`.
- Produces: `CreateUserRequest.password: str` (`min_length=8`, `max_length=128`, **không** `strip`); `UserService.create_user(actor, *, email, name, role, password) -> User`. Audit log `diff` **không** chứa mật khẩu/hash. Response vẫn là `User`.

- [x] **Step 1: Viết test đỏ:** `test_create_user_with_password_can_log_in` (tạo bằng Admin, rồi trình duyệt khác đăng nhập được), `test_create_user_requires_password_422`, `test_short_password_422_and_nothing_saved`, `test_too_long_password_422`, `test_response_has_no_hash_or_password`, `test_audit_log_has_no_password_or_hash`. Sửa các test tạo user cũ truyền `password`.
- [x] **Step 2: Chạy** `uv run pytest tests/test_users_api.py -q` → FAIL.
- [x] **Step 3: Implement** như Interfaces.
- [x] **Step 4: Chạy** → PASS.
- [x] **Step 5: Commit** `feat(users): Admin tạo user kèm mật khẩu tạm`.

### Task 6: Đổi mật khẩu và đặt lại mật khẩu (xoá session)

**Files:**
- Modify: `backend/app/api/sessions.py`, `backend/app/api/routers/auth.py`, `backend/app/api/routers/users.py`, `backend/app/core/services/users.py`
- Test: `backend/tests/test_sessions.py` (hoặc file test session hiện có), `backend/tests/test_auth.py`, `backend/tests/test_users_api.py`

**Interfaces:**
- Produces:
  - `SessionStore.delete_all_for(email: str) -> None` — xoá mọi session của email đó. Cách làm: khi `create` thêm session id vào tập Redis `user_sessions:{email}` (cùng TTL), `delete_all_for` xoá từng key `session:{id}` rồi xoá tập.
  - `POST /api/auth/change-password` body `{current_password, new_password}` (người đang đăng nhập): sai mật khẩu hiện tại → `400 {"detail": "Mật khẩu hiện tại không đúng"}` (và tính vào bộ đếm chống dò); đúng → ghi hash mới, xoá mọi session cũ, tạo session mới và đặt cookie mới cho trình duyệt hiện tại; trả `204`.
  - `POST /api/users/{email}/reset-password` body `{password}` (chỉ `Action.MANAGE_USERS`): đặt hash mới, `delete_all_for(email)`, ghi audit log `action="RESET_PASSWORD"` (diff rỗng, không có hash), trả `204`; không có user → `404 "Không tìm thấy người dùng"`.
  - Mật khẩu mới: `min_length=8`, `max_length=128`, không `strip`.

- [x] **Step 1: Viết test đỏ:** `test_delete_all_for_removes_every_session_of_that_user_only`; `test_change_password_success_old_password_stops_working` + `test_change_password_keeps_current_browser_logged_in` + `test_change_password_logs_out_other_browsers`; `test_change_password_wrong_current_400`; `test_change_password_wrong_current_counts_toward_lock`; `test_change_password_short_new_422`; `test_change_password_requires_login_401`; `test_reset_password_admin_only_403_for_tester`; `test_reset_password_logs_out_target_and_new_password_works`; `test_reset_password_unknown_user_404`; `test_reset_own_password_as_admin_works`; `test_reset_password_for_inactive_user_still_cannot_log_in`; `test_reset_password_audit_has_no_password`.
- [x] **Step 2: Chạy** các file test trên → FAIL.
- [x] **Step 3: Implement** như Interfaces (logic nghiệp vụ trong `UserService`/`core/services/auth.py`, router mỏng).
- [x] **Step 4: Chạy** → PASS.
- [x] **Step 5: Commit** `feat(auth): đổi mật khẩu và Admin đặt lại mật khẩu, xoá phiên cũ`.

### Task 7: Gỡ hẳn Google OAuth

**Files:**
- Delete: `backend/app/api/oauth.py`
- Modify: `backend/app/api/services.py` (bỏ `oauth` khỏi `Services`/`build_services`), `backend/app/settings.py` (bỏ `google_client_id`, `google_client_secret`), `backend/app/main.py` (bỏ `SessionMiddleware`; giữ `SESSION_SECRET` như cũ, không động tới), `backend/tests/conftest.py`, `backend/tests/fakes.py` (xoá `FakeOAuth`), `backend/pyproject.toml` (`uv remove authlib`; xoá `itsdangerous`/`httpx` chỉ khi không còn nơi nào dùng — kiểm bằng Grep), mọi test còn tham số `oauth`
- Test: toàn bộ `backend/tests`

- [x] **Step 1: Viết test đỏ:** `test_openapi_has_no_oauth_paths` — `/openapi.json` không có `/api/auth/callback`; chỉ có `/api/auth/login` kiểu POST.
- [x] **Step 2: Chạy** → FAIL.
- [x] **Step 3: Implement** như Files. Dùng Grep `oauth|OAuth|GoogleIdentity|FakeOAuth|authlib` trong `backend/` để dọn sạch (trừ `google.oauth2.service_account` trong `gateway.py`, là Service Account, phải giữ). Cập nhật `backend/export_openapi.py` nếu nó tham chiếu OAuth.
- [x] **Step 4: Chạy** `uv run pytest -q && uv run mypy app && uv run ruff check` → sạch.
- [x] **Step 5: Commit** `refactor(auth): gỡ Google OAuth khỏi backend`.

- [x] **Cuối đợt 2 (xong 2026-11-17, backend 604 test qua):** tick các task, ghi tiến độ vào `HANDOFF.md`, dừng cho `/compact`.

---

## ĐỢT 3 — Frontend

> Trước khi viết: đọc `frontend/AGENTS.md`. Sau khi backend xong, chạy `cd frontend && npm run gen:api` để cập nhật kiểu API.

### Task 8: Trang đăng nhập bằng email + mật khẩu

**Files:**
- Modify: `frontend/app/login/login-card.tsx`, `frontend/messages/vi.json` (nhóm `login`)
- Delete: `frontend/lib/login-error.ts`, `frontend/lib/login-error.test.ts` (nếu không còn dùng)
- Test: `frontend/app/login/login-card.test.tsx` (tạo mới nếu chưa có)

**Interfaces:**
- Consumes: `POST /api/auth/login` (`200` → chuyển về `/`; `401`/`429` → hiện `detail` từ server, không tự bịa câu).
- Produces: form có ô email, ô mật khẩu (`type="password"`), nút "Đăng nhập", trạng thái đang gửi (nút mờ), hiện lỗi. Bỏ nút Google và chuỗi `oauthFailed`, `not_allowed`.

- [ ] **Step 1: Viết test đỏ:** `renders email and password fields, no Google button`; `submits credentials and redirects home on 200`; `shows server message on 401`; `shows lock message on 429`; `disables button while submitting`.
- [ ] **Step 2: Chạy** `npx vitest run app/login` → FAIL.
- [ ] **Step 3: Implement** form; chuỗi vào `vi.json`.
- [ ] **Step 4: Chạy** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): trang đăng nhập bằng email và mật khẩu`.

### Task 9: Tạo user có mật khẩu và nút "Đặt lại mật khẩu"

**Files:**
- Modify: `frontend/components/users/user-form-dialog.tsx`, `user-form-schema.ts`, `user-table.tsx`, `use-users.ts`, `frontend/messages/vi.json` (nhóm `users`; sửa `formDescription` đang nhắc email Google)
- Create: `frontend/components/users/reset-password-dialog.tsx`
- Test: `user-form-schema.test.ts`, `user-table.test.tsx`, `reset-password-dialog.test.tsx`

**Interfaces:**
- Consumes: `POST /api/users` (có `password`), `POST /api/users/{email}/reset-password`.
- Produces: schema form thêm `password` (8–128 ký tự, thông báo tiếng Việt); `useResetPassword()` mutation; hộp thoại đặt lại mật khẩu, nút ở mỗi hàng của bảng (Admin).

- [ ] **Step 1: Viết test đỏ:** `schema rejects password shorter than 8`; `form sends password when creating`; `table shows reset-password button per user`; `reset dialog validates length and calls the API`; `reset dialog shows 404 message`.
- [ ] **Step 2: Chạy** `npx vitest run components/users` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): tạo user kèm mật khẩu và đặt lại mật khẩu`.

### Task 10: Mục "Đổi mật khẩu" cho mọi người

**Files:**
- Create: `frontend/components/account/change-password-dialog.tsx` (+ test)
- Modify: `frontend/components/app-shell/sidebar.tsx` (hoặc nơi hiển thị người dùng/đăng xuất; đọc file để chọn chỗ hợp lý), `frontend/messages/vi.json`

**Interfaces:**
- Consumes: `POST /api/auth/change-password`.
- Produces: hộp thoại 3 ô (mật khẩu hiện tại, mới, nhập lại mới); kiểm tra khớp và ≥8 ký tự ở client; `400` hiện `detail`; thành công thì đóng và báo "Đã đổi mật khẩu".

- [ ] **Step 1: Viết test đỏ:** `requires matching confirmation`; `rejects short new password`; `shows server error on wrong current password`; `closes and shows success on 204`; `sidebar opens the dialog`.
- [ ] **Step 2: Chạy** `npx vitest run components/account components/app-shell` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy** đủ `npx vitest run && npm run typecheck && npm run lint` → sạch.
- [ ] **Step 5: Commit** `feat(frontend): người dùng tự đổi mật khẩu`.

- [ ] **Cuối đợt 3:** tick, ghi `HANDOFF.md`, dừng cho `/compact`.

---

## ĐỢT 4 — Tài liệu và dọn cấu hình

### Task 11: Cập nhật tài liệu và `.env.example`

**Files:**
- Modify: `SETUP.md` (bỏ bước 1.3 và 1.4, bỏ biến Google OAuth, thêm `BOOTSTRAP_ADMIN_PASSWORD` và cách cấp mật khẩu cho thành viên), `README.md`, `docs/architecture.md`, `HANDOFF.md` (ghi đã đổi sang mật khẩu, bỏ OAuth), `.env.example` (bỏ `GOOGLE_CLIENT_ID/SECRET`, thêm `BOOTSTRAP_ADMIN_PASSWORD=`), `docker-compose*.yml` nếu truyền các biến Google (kiểm bằng Grep)

- [ ] **Step 1:** Grep `GOOGLE_CLIENT|OAuth|đăng nhập Google|authlib` trong các file `.md`, `.example`, compose; liệt kê chỗ cần sửa.
- [ ] **Step 2:** Sửa từng chỗ; giữ mọi nội dung về Service Account.
- [ ] **Step 3:** Chạy lại Grep bước 1 → chỉ còn nhắc tới OAuth ở tài liệu lịch sử (`docs/superpowers/specs|plans` cũ, không sửa).
- [ ] **Step 4:** Chạy đủ hai bộ kiểm tra (Global Constraints) → sạch.
- [ ] **Step 5: Commit** `docs: đổi hướng dẫn sang đăng nhập bằng mật khẩu`.

### Task 12: Kiểm tra cuối và bàn giao

- [ ] **Step 1:** Chạy đủ `pytest`, `mypy`, `ruff`, `vitest`, `typecheck`, `lint`; ghi số test vào `HANDOFF.md`.
- [ ] **Step 2:** Grep toàn repo tìm `password_hash` trong `backend/app/api` → chỉ được xuất hiện nếu là tên biến nội bộ, không nằm trong model/response nào.
- [ ] **Step 3:** Báo chủ dự án: tên biến `.env` đúng (`BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`), không dùng mật khẩu Gmail thật, và Admin cũ sẽ được đặt hash ở lần khởi động đầu. Không push.
- [ ] **Step 4: Commit** `docs: ghi tiến độ đăng nhập bằng mật khẩu vào HANDOFF`.

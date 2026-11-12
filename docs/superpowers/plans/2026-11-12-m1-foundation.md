# M1 — Nền tảng: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng khung dự án chạy được bằng `docker compose up`: đăng nhập Google, lớp đọc/ghi Google Sheets an toàn (ánh xạ theo tên cột, retry, khoá Redis, cache), phân quyền theo bảng, quản lý user cho Admin, và khung giao diện tiếng Việt.

**Architecture:** `backend/` là một project Python (FastAPI). Code đồng bộ (sync), các endpoint khai báo `def` để FastAPI chạy trong threadpool. Mọi truy cập Sheets đi qua `SheetsGateway` (lớp mỏng bọc Google API), rồi `SheetTable` (ánh xạ theo tên cột), rồi các repository. `frontend/` là Next.js; mọi `/api/*` được proxy sang FastAPI nên cookie dùng chung một origin (`http://localhost:3000`).

**Tech Stack:** Python 3.13, uv, FastAPI, Pydantic v2, pydantic-settings, google-api-python-client + google-auth, Authlib (OAuth client), redis-py, pytest, fakeredis, mypy --strict, ruff · Next.js (App Router, TypeScript strict), Tailwind, shadcn/ui, next-intl, next-themes, TanStack Query, openapi-typescript + openapi-fetch, Zod, Vitest · Docker Compose, Redis 7.

**Spec:** `docs/superpowers/specs/2026-11-12-ai-test-runner-design.md` (mục 4, 6, 7.1, 7.2, 8.1, 9, 11, 12, 13, 14, 15.1)

## Global Constraints

- Làm trên nhánh `m1-foundation`. Commit sau mỗi task. **Không push** lên GitHub.
- Python ≥ 3.12 (image Docker `python:3.13-slim`); Node 24 (image `node:24-alpine`).
- `mypy --strict` và `ruff check` sạch cho `backend/`; TypeScript `strict: true`.
- Router và service **không** import `googleapiclient`. Chỉ `backend/app/core/sheets/gateway.py` được import.
- Sheet ánh xạ theo **tên cột** (hàng 1). Không bao giờ dùng số dòng đã lưu từ trước; mỗi lần ghi đều tìm lại dòng.
- Giao diện tiếng Việt. Mọi chuỗi hiển thị nằm trong `frontend/messages/vi.json`, không viết cứng trong component.
- Secret chỉ nằm ở backend. Frontend chỉ biết `API_INTERNAL_URL`.
- Không log payload của người dùng. Log chỉ chứa id, email người thao tác, hành động.
- Thông báo lỗi trả về dạng `{"detail": "<câu tiếng Việt>"}`.
- Ghi mọi giả định mới vào cuối `DECISIONS.md`.
- Code dễ đọc: tên đầy đủ, hàm ngắn, thoát sớm. Có thể dùng skill `reviewing-readable-code` để tự soát.

## Review Focus

1. **Dòng Sheet thiếu ô cuối hoặc dòng trống** (Google bỏ các ô trống cuối dòng): phải đệm cho đủ cột và bỏ qua dòng trống, không được crash. Test nằm ở Task 2.
2. **Email khác hoa/thường hoặc dư khoảng trắng** (`" An@Gmail.com"`): phải chuẩn hoá `strip().lower()` ở mọi chỗ nhận email (đăng nhập, tạo user, tìm user). Test ở Task 5 và Task 6.
3. **Admin tự khoá hoặc tự hạ quyền chính mình**: trả 400, để hệ thống không mất Admin cuối cùng. Test ở Task 6.
4. **Cột trong Sheet bị đổi thứ tự hoặc có cột lạ**: vẫn đọc và ghi đúng. Thiếu cột bắt buộc thì báo lỗi rõ ràng tên cột thiếu. Test ở Task 2.
5. **User bị khoá trong lúc đang đăng nhập**: request tiếp theo phải nhận 401, vì cache user bị xoá khi ghi. Test ở Task 5.

---

## File Structure

```
/
├── .gitignore  .env.example  README.md  DECISIONS.md  docker-compose.yml
├── backend/
│   ├── pyproject.toml  Dockerfile
│   ├── app/
│   │   ├── main.py                     # tạo FastAPI app, gắn router, chạy bootstrap khi khởi động
│   │   ├── settings.py                 # đọc biến môi trường
│   │   ├── core/
│   │   │   ├── models/user.py          # Role, User
│   │   │   ├── sheets/gateway.py       # SheetsGateway (Protocol) + GoogleSheetsGateway + with_retry
│   │   │   ├── sheets/table.py         # SheetTable: ánh xạ theo tên cột
│   │   │   ├── sheets/schema.py        # tên tab + danh sách cột của file Sheet hệ thống
│   │   │   ├── locks/redis_lock.py     # redis_lock(), LockTimeout
│   │   │   ├── repositories/users.py   # UserRepository (có cache)
│   │   │   ├── repositories/audit_log.py
│   │   │   ├── services/users.py       # UserService: tạo/sửa user, tính diff, ghi audit
│   │   │   ├── permissions.py          # Action, can()
│   │   │   └── bootstrap.py            # tạo tab còn thiếu + Admin đầu tiên
│   │   └── api/
│   │       ├── deps.py                 # get_current_user, require()
│   │       ├── sessions.py             # SessionStore (Redis)
│   │       ├── routers/health.py  auth.py  users.py
│   │       └── errors.py
│   └── tests/
│       ├── fakes.py                    # FakeSheetsGateway
│       └── test_*.py
└── frontend/
    ├── Dockerfile  next.config.ts  package.json
    ├── messages/vi.json
    ├── i18n/request.ts
    ├── app/
    │   ├── layout.tsx  providers.tsx
    │   ├── login/page.tsx
    │   └── (app)/layout.tsx  page.tsx  admin/users/page.tsx
    ├── components/
    │   ├── app-shell/sidebar.tsx  topbar.tsx  theme-toggle.tsx
    │   └── users/user-table.tsx  user-form-dialog.tsx
    └── lib/
        ├── api/client.ts  schema.d.ts  use-me.ts
        └── nav.ts                      # các mục menu và vai trò được thấy
```

---

### Task 1: Khung backend + health check

**Files:**
- Create: `.gitignore`, `.env.example`, `DECISIONS.md`, `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/settings.py`, `backend/app/api/routers/health.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `Settings` (pydantic-settings) với các trường của mục 14 trong spec, cộng thêm `session_ttl_seconds: int = 604800`, `user_cache_ttl_seconds: int = 300`. Hàm `get_settings() -> Settings` có `lru_cache`. Hàm `create_app(settings: Settings | None = None) -> FastAPI`. Router health ở `GET /api/health` trả về `{"status": "ok"}`.

- [ ] **Step 1:** `git checkout -b m1-foundation`. Tạo `.gitignore`: `.env`, `__pycache__/`, `.venv/`, `node_modules/`, `.next/`, `*.json.key`, `.claude/`.
- [ ] **Step 2:** Viết `.env.example`, chép đúng mục 14 của spec. Bỏ các dòng chỉ cần từ M2 trở đi nhưng giữ comment `# dùng từ M2/M4`. Thêm `API_INTERNAL_URL=http://localhost:8000`. Tạo `DECISIONS.md` với tiêu đề `# Các quyết định và giả định` và mục đầu tiên: "Backend viết đồng bộ (sync), endpoint `def`, để code đơn giản và dễ đọc".
- [ ] **Step 3:** `cd backend && uv init --app --name ai-test-runner-backend`, rồi `uv add fastapi uvicorn[standard] pydantic-settings google-api-python-client google-auth authlib httpx redis itsdangerous` và `uv add --dev pytest mypy ruff fakeredis types-redis`. Trong `pyproject.toml`, cấu hình `[tool.mypy] strict = true`, `[tool.ruff] line-length = 100`, `[tool.pytest.ini_options] pythonpath = ["."]`.
- [ ] **Step 4: Viết test fail**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import create_app

def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5:** `uv run pytest tests/test_health.py -v`. Kỳ vọng: FAIL (`ModuleNotFoundError: app.main`).
- [ ] **Step 6:** Viết `settings.py`, `main.py`, `routers/health.py`. Trong bản test, `create_app()` không được đòi hỏi biến môi trường: mọi trường của `Settings` có giá trị mặc định rỗng, và việc kiểm tra cấu hình bắt buộc chỉ chạy trong bootstrap (Task 7).
- [ ] **Step 7:** `uv run pytest -v && uv run mypy app && uv run ruff check .`. Kỳ vọng: tất cả PASS.
- [ ] **Step 8:** Commit `chore: scaffold backend with health check`.

---

### Task 2: Gateway Google Sheets, retry, và SheetTable ánh xạ theo tên cột

**Files:**
- Create: `backend/app/core/sheets/gateway.py`, `backend/app/core/sheets/table.py`, `backend/tests/fakes.py`, `backend/tests/test_sheets_retry.py`, `backend/tests/test_sheet_table.py`

**Interfaces:**
- Produces:
  ```python
  class SheetsGateway(Protocol):
      def get_values(self, spreadsheet_id: str, a1_range: str) -> list[list[str]]: ...
      def append_rows(self, spreadsheet_id: str, tab: str, rows: list[list[str]]) -> None: ...
      def update_row(self, spreadsheet_id: str, tab: str, row_number: int, values: list[str]) -> None: ...
      def list_tabs(self, spreadsheet_id: str) -> list[str]: ...
      def add_tab(self, spreadsheet_id: str, tab: str, header: list[str]) -> None: ...

  class GoogleSheetsGateway:  # cài đặt thật, mỗi lời gọi bọc trong with_retry
      def __init__(self, service_account_info: dict[str, Any]) -> None: ...

  def with_retry(call: Callable[[], T], *, max_attempts: int = 5, base_delay_seconds: float = 0.5,
                 sleep: Callable[[float], None] = time.sleep) -> T: ...

  class MissingColumnsError(Exception): ...  # message liệt kê tên cột thiếu

  class SheetTable:
      def __init__(self, gateway: SheetsGateway, spreadsheet_id: str, tab: str,
                   columns: list[str]) -> None: ...
      def read_all(self) -> list[dict[str, str]]: ...
      def find_row_number(self, column: str, value: str) -> int | None: ...  # số dòng 1-based trong Sheet
      def read_row(self, row_number: int) -> dict[str, str]: ...
      def append(self, record: dict[str, str]) -> None: ...
      def update(self, row_number: int, record: dict[str, str]) -> None: ...
  ```
- `tests/fakes.py`: `FakeSheetsGateway` lưu dữ liệu trong `dict[spreadsheet_id][tab] -> list[list[str]]`, hiểu được các range `Tab`, `Tab!1:1`, `Tab!C:C`, `Tab!5:5`. Khi trả về, nó **cắt các ô trống ở cuối dòng** giống Google thật.

- [ ] **Step 1: Test retry (viết trước)**

```python
def test_retry_on_429_then_success() -> None:
    calls = {"count": 0}
    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise make_http_error(429)
        return "ok"
    delays: list[float] = []
    assert with_retry(flaky, sleep=delays.append) == "ok"
    assert len(delays) == 2 and delays[1] > delays[0]   # backoff tăng dần

def test_retry_gives_up_after_max_attempts() -> None: ...   # raise HttpError 503 sau 5 lần
def test_no_retry_on_404() -> None: ...                     # gọi đúng 1 lần
```
`make_http_error(status)` là helper trong `fakes.py`, tạo `googleapiclient.errors.HttpError` với `resp.status`.

- [ ] **Step 2: Test SheetTable (viết trước)**

```python
COLUMNS = ["email", "name", "role", "active", "created_at"]

def test_reads_by_column_name_when_columns_reordered() -> None:
    gateway = FakeSheetsGateway({"sys": {"Users": [
        ["role", "email", "extra", "name", "active", "created_at"],
        ["ADMIN", "a@x.com", "?", "An", "TRUE", "2026-11-12T00:00:00Z"]]}})
    table = SheetTable(gateway, "sys", "Users", COLUMNS)
    assert table.read_all() == [{"email": "a@x.com", "name": "An", "role": "ADMIN",
                                 "active": "TRUE", "created_at": "2026-11-12T00:00:00Z"}]

def test_pads_short_rows_and_skips_blank_rows() -> None: ...
    # dòng ["b@x.com", "Bình"] → các cột còn lại là ""; dòng [] bị bỏ qua

def test_missing_column_raises_clear_error() -> None:
    # header thiếu "role" → MissingColumnsError, và "role" có trong message

def test_find_row_number_reads_only_that_column() -> None:
    # find_row_number("email", "b@x.com") == 3; gateway.calls chứa "Users!B:B" (đúng cột email)

def test_update_writes_values_in_sheet_column_order_and_keeps_unknown_columns() -> None:
    # update(2, record) → dòng 2 theo đúng thứ tự header; giá trị ở cột "extra" giữ nguyên
```

- [ ] **Step 3:** `uv run pytest tests/test_sheets_retry.py tests/test_sheet_table.py -v`. Kỳ vọng: FAIL (chưa có module).
- [ ] **Step 4:** Cài đặt `with_retry`. Retry khi status là 429 hoặc ≥ 500. Thời gian chờ `base * 2**attempt + random.uniform(0, base)`.
- [ ] **Step 5:** Cài đặt `SheetTable`. Đọc header (`Tab!1:1`) một lần cho mỗi instance. Đổi chỉ số cột sang chữ cái (A, B, …, Z, AA…) bằng hàm riêng `column_letter(index: int) -> str`, có test riêng cho `0→A`, `25→Z`, `26→AA`. Khi `update`, đọc lại dòng hiện tại để giữ nguyên giá trị các cột không thuộc `columns`.
- [ ] **Step 6:** Cài đặt `GoogleSheetsGateway`. Client của googleapiclient không an toàn khi dùng chung giữa nhiều thread, nên tạo service riêng cho mỗi thread bằng `threading.local()`. Ghi giá trị với `valueInputOption="RAW"`. Lớp này không có unit test (sẽ chạy thật ở Task 9).
- [ ] **Step 7:** `uv run pytest -v && uv run mypy app && uv run ruff check .`. Kỳ vọng: PASS.
- [ ] **Step 8:** Commit `feat(core): add Sheets gateway with retry and column-name table`.

---

### Task 3: Khoá Redis

**Files:**
- Create: `backend/app/core/locks/redis_lock.py`, `backend/tests/test_redis_lock.py`

**Interfaces:**
- Produces:
  ```python
  class LockTimeout(Exception): ...
  @contextmanager
  def redis_lock(redis: Redis, key: str, *, ttl_seconds: int = 10,
                 wait_seconds: float = 5.0, poll_seconds: float = 0.05) -> Iterator[None]: ...
  ```
  Tên khoá theo spec: `lock:<project_id>:<entity>:<id>`. Với dữ liệu hệ thống dùng `lock:system:<entity>:<id>`.

- [ ] **Step 1: Test (dùng `fakeredis.FakeRedis()`)**

```python
def test_second_holder_waits_and_times_out() -> None:
    redis = fakeredis.FakeRedis()
    with redis_lock(redis, "lock:system:user:a@x.com"):
        with pytest.raises(LockTimeout):
            with redis_lock(redis, "lock:system:user:a@x.com", wait_seconds=0.1):
                pass

def test_lock_released_after_block() -> None: ...           # khoá lại được ngay sau khi thoát khối with
def test_release_does_not_delete_someone_elses_lock() -> None:
    # khoá hết TTL, người khác lấy khoá; người cũ thoát khối with thì KHÔNG được xoá khoá của người mới
def test_two_threads_never_inside_together() -> None:
    # 2 thread × 20 lần vào/ra; một bộ đếm "đang ở trong" không bao giờ vượt quá 1
```

- [ ] **Step 2:** Chạy, kỳ vọng FAIL.
- [ ] **Step 3:** Cài đặt. Lấy khoá bằng `SET key token NX PX ttl`. Nhả khoá bằng script Lua, chỉ `DEL` khi giá trị bằng token của mình.
- [ ] **Step 4:** Chạy pytest, mypy, ruff. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(core): add Redis lock`.

---

### Task 4: Model User, UserRepository (có cache), AuditLogRepository

**Files:**
- Create: `backend/app/core/models/user.py`, `backend/app/core/sheets/schema.py`, `backend/app/core/repositories/users.py`, `backend/app/core/repositories/audit_log.py`, `backend/tests/test_user_repository.py`, `backend/tests/test_audit_log_repository.py`

**Interfaces:**
- Consumes: `SheetTable`, `SheetsGateway`, `redis_lock` (Task 2–3).
- Produces:
  ```python
  class Role(StrEnum): ADMIN = "ADMIN"; QA_LEAD = "QA_LEAD"; TESTER = "TESTER"; VIEWER = "VIEWER"
  class User(BaseModel): email: str; name: str; role: Role; active: bool; created_at: datetime
  def normalize_email(email: str) -> str   # strip().lower()

  # schema.py
  SYSTEM_TABS: dict[str, list[str]]  # "Users", "Projects", "ProjectMembers", "AuditLog" → cột theo mục 8.1

  class UserAlreadyExistsError(Exception): ...
  class UserNotFoundError(Exception): ...
  class UserRepository:
      def __init__(self, gateway: SheetsGateway, spreadsheet_id: str, redis: Redis,
                   cache_ttl_seconds: int) -> None: ...
      def list_all(self) -> list[User]: ...
      def get(self, email: str) -> User | None: ...   # tự chuẩn hoá email
      def create(self, user: User) -> User: ...       # lỗi UserAlreadyExistsError
      def update(self, user: User) -> User: ...       # lỗi UserNotFoundError; tìm dòng theo email ngay trong khoá
      def is_empty(self) -> bool: ...

  class AuditLogRepository:
      def __init__(self, gateway: SheetsGateway, spreadsheet_id: str) -> None: ...
      def record(self, *, actor: str, action: str, entity: str, entity_id: str,
                 diff: dict[str, Any]) -> None: ...   # cột `at` là UTC ISO; diff_json là json.dumps(ensure_ascii=False)
  ```
- Trên Sheet, `active` được lưu là `"TRUE"`/`"FALSE"`; khi đọc chấp nhận cả `true`/`FALSE`/`1`. Cache: key `cache:users`, chứa danh sách user dạng JSON, TTL theo cấu hình, **xoá** sau mỗi `create`/`update`.

- [ ] **Step 1: Test**

```python
def test_get_normalizes_email(repo) -> None:
    repo.create(make_user("an@x.com"))
    assert repo.get("  AN@X.com ") is not None

def test_create_duplicate_raises(repo) -> None: ...
def test_update_finds_row_by_email_even_after_rows_inserted_above(repo, gateway) -> None:
    # tạo 2 user; chèn tay một dòng vào ngay dưới header; update user thứ 2 → đúng dòng đó bị sửa
def test_list_uses_cache_then_invalidates_on_write(repo, gateway) -> None:
    # list_all() hai lần → gateway chỉ đọc tab Users 1 lần; sau update → lần list_all() kế tiếp đọc lại
def test_create_takes_lock(repo, redis) -> None:
    # đang giữ lock:system:user:an@x.com bằng tay → create(an@x.com) raise LockTimeout (wait_seconds nhỏ)
def test_audit_record_appends_row_with_json_diff() -> None: ...
```

- [ ] **Step 2:** Chạy, kỳ vọng FAIL.
- [ ] **Step 3:** Cài đặt. Khoá cho user là `lock:system:user:<email>`.
- [ ] **Step 4:** Chạy pytest, mypy, ruff. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(core): add user and audit log repositories`.

---

### Task 5: Phân quyền, session, đăng nhập Google, `/api/me`

**Files:**
- Create: `backend/app/core/permissions.py`, `backend/app/api/sessions.py`, `backend/app/api/deps.py`, `backend/app/api/errors.py`, `backend/app/api/routers/auth.py`, `backend/tests/test_permissions.py`, `backend/tests/test_auth.py`, `backend/tests/conftest.py`
- Modify: `backend/app/main.py` (gắn router; dependency để test thay được gateway và redis)

**Interfaces:**
- Consumes: `User`, `Role`, `UserRepository`, `normalize_email`.
- Produces:
  ```python
  class Action(StrEnum):
      MANAGE_USERS; MANAGE_PROJECTS; MANAGE_MEMBERS; MANAGE_SCREENS; EDIT_TEST_CASE
      REVIEW_TEST_CASE; TRIGGER_RUN; REVIEW_RESULTS; VIEW_PROJECT
  def can(user: User, action: Action, *, is_member: bool = False,
          owns_or_assigned: bool = False) -> bool

  class SessionStore:
      def __init__(self, redis: Redis, ttl_seconds: int) -> None: ...
      def create(self, email: str) -> str: ...        # session id = secrets.token_urlsafe(32); key "session:<id>"
      def get_email(self, session_id: str) -> str | None: ...   # mỗi lần đọc thì gia hạn TTL
      def delete(self, session_id: str) -> None: ...

  SESSION_COOKIE = "atr_session"
  def get_current_user(...) -> User          # 401 "Bạn cần đăng nhập" nếu không có/sai session; 401 nếu user không còn hoặc bị khoá
  def require(user: User, action: Action, *, is_member: bool = False,
              owns_or_assigned: bool = False) -> None   # 403 "Bạn không có quyền thực hiện thao tác này"
  def authenticate(users: UserRepository, email: str) -> User | None   # None nếu không có trong Users hoặc active = FALSE
  ```
- Routes: `GET /api/auth/login` (chuyển hướng sang Google), `GET /api/auth/callback` (thành công: đặt cookie rồi chuyển về `/`; email không được phép: chuyển về `/login?error=not_allowed`), `POST /api/auth/logout` (204), `GET /api/me` (trả về `User`).
- Cookie: `httponly=True`, `samesite="lax"`, `secure = APP_BASE_URL.startswith("https")`, `max_age = session_ttl_seconds`. Redirect URI cho Google: `{APP_BASE_URL}/api/auth/callback`. OAuth state được giữ qua `SessionMiddleware` của Starlette (dùng `SESSION_SECRET`).

- [ ] **Step 1: Test bảng phân quyền.** Viết dạng parametrize, phủ **toàn bộ** bảng ở mục 4 của spec (4 vai trò × 9 hành động), cộng các trường hợp riêng:

```python
@pytest.mark.parametrize(("role", "action", "is_member", "owns", "expected"), [
    (Role.ADMIN, Action.MANAGE_USERS, False, False, True),
    (Role.QA_LEAD, Action.MANAGE_USERS, True, False, False),
    (Role.QA_LEAD, Action.MANAGE_SCREENS, True, False, True),
    (Role.QA_LEAD, Action.MANAGE_SCREENS, False, False, False),   # QA Lead không phải thành viên
    (Role.TESTER, Action.EDIT_TEST_CASE, True, True, True),
    (Role.TESTER, Action.EDIT_TEST_CASE, True, False, False),     # không phải case của mình, không được giao
    (Role.VIEWER, Action.VIEW_PROJECT, True, False, True),
    (Role.VIEWER, Action.VIEW_PROJECT, False, False, False),
    (Role.ADMIN, Action.VIEW_PROJECT, False, False, True),        # Admin thấy mọi dự án
    # ... đủ 36 tổ hợp chính
])
def test_permission_matrix(...) -> None: ...
def test_inactive_user_can_do_nothing() -> None: ...
```

- [ ] **Step 2: Test đăng nhập và session.** Không gọi Google thật: test thay hàm đổi mã OAuth bằng một dependency giả, trả về `{"email": ..., "name": ...}`.

```python
def test_callback_allowed_user_sets_cookie_and_redirects_home(client, users) -> None:
    # email "  An@X.com" khớp user "an@x.com" active → 302 về "/", có Set-Cookie atr_session, có HttpOnly
def test_callback_unknown_email_redirects_to_login_error(client) -> None: ...   # Location: /login?error=not_allowed
def test_callback_inactive_user_rejected(client, users) -> None: ...
def test_me_without_cookie_is_401(client) -> None: ...
def test_me_returns_user(logged_in_client) -> None: ...
def test_user_deactivated_after_login_gets_401_next_request(logged_in_client, users) -> None:
    # users.update(... active=False) → GET /api/me trả 401
def test_logout_deletes_session(logged_in_client) -> None: ...
```

- [ ] **Step 3:** Chạy, kỳ vọng FAIL.
- [ ] **Step 4:** Cài đặt `permissions.py`, dịch nguyên bảng mục 4 thành một dict `ALLOWED: dict[Action, set[Role]]`, cộng hai luật: (a) mọi hành động trong dự án, trừ với Admin, đòi `is_member`; (b) Tester sửa case đòi `owns_or_assigned`. Sau đó cài đặt `sessions.py`, `deps.py`, `auth.py`.
- [ ] **Step 5:** Chạy pytest, mypy, ruff. Kỳ vọng: PASS.
- [ ] **Step 6:** Commit `feat(api): add Google login, sessions and permission checks`.

---

### Task 6: API quản lý user (Admin)

**Files:**
- Create: `backend/app/api/routers/users.py`, `backend/tests/test_users_api.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `require(user, Action.MANAGE_USERS)`, `UserRepository`, `AuditLogRepository`.
- Produces (OpenAPI; frontend sinh kiểu TypeScript từ đây):
  - `GET /api/users` trả về `list[User]`.
  - `POST /api/users` nhận `CreateUserRequest {email: EmailStr, name: str (1..100), role: Role}`, trả 201 kèm `User`. Email đã có thì 409 "Email này đã có trong hệ thống".
  - `PATCH /api/users/{email}` nhận `UpdateUserRequest {name?: str, role?: Role, active?: bool}`, trả 200 kèm `User`. Không có thì 404 "Không tìm thấy người dùng".
  - Admin tự khoá mình hoặc tự hạ quyền mình thì 400 "Bạn không thể tự khoá hoặc tự hạ quyền của chính mình".
  - Lock timeout thì 409 "Dữ liệu đang được người khác cập nhật, vui lòng thử lại".
  - Mỗi lần tạo/sửa ghi `AuditLog`: `entity="user"`, `action` là `CREATE`/`UPDATE`, `diff` chỉ chứa các trường thay đổi dạng `{field: [cũ, mới]}`.

- [ ] **Step 1: Test**

```python
def test_non_admin_gets_403(client_as_qa_lead) -> None: ...          # cả GET, POST, PATCH
def test_create_user_normalizes_email_and_audits(client_as_admin, gateway) -> None:
    # POST email "  Binh@X.com " → 201, email "binh@x.com"; AuditLog có 1 dòng CREATE
def test_create_duplicate_is_409(client_as_admin) -> None: ...
def test_create_invalid_email_is_422(client_as_admin) -> None: ...
def test_patch_role_and_deactivate(client_as_admin) -> None: ...      # diff chỉ chứa role và active
def test_admin_cannot_deactivate_or_demote_self(client_as_admin) -> None: ...   # 400
def test_patch_unknown_user_is_404(client_as_admin) -> None: ...
```

- [ ] **Step 2:** Chạy, kỳ vọng FAIL.
- [ ] **Step 3:** Cài đặt router. Gom phần nghiệp vụ (tạo, sửa, tính diff, audit) vào `app/core/services/users.py` (`UserService`); router chỉ kiểm tra quyền và gọi service.
- [ ] **Step 4:** Chạy pytest, mypy, ruff. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(api): add user management endpoints`.

---

### Task 7: Bootstrap file Sheet hệ thống

**Files:**
- Create: `backend/app/core/bootstrap.py`, `backend/tests/test_bootstrap.py`
- Modify: `backend/app/main.py` (gọi bootstrap trong `lifespan`, chỉ khi `SYSTEM_SPREADSHEET_ID` có giá trị)

**Interfaces:**
- Produces: `bootstrap_system_spreadsheet(gateway: SheetsGateway, spreadsheet_id: str, users: UserRepository, bootstrap_admin_email: str) -> list[str]`, trả về danh sách tab vừa tạo. Thêm `class ConfigError(Exception)` cho trường hợp thiếu cấu hình bắt buộc khi chạy thật.

- [ ] **Step 1: Test**

```python
def test_creates_missing_tabs_with_headers() -> None:
    # sheet chỉ có "Users" → tạo "Projects", "ProjectMembers", "AuditLog" với header đúng SYSTEM_TABS
def test_adds_bootstrap_admin_when_users_empty() -> None: ...   # role ADMIN, active TRUE, email đã chuẩn hoá
def test_does_not_add_admin_when_users_exist() -> None: ...
def test_existing_tab_with_missing_column_raises() -> None: ...   # MissingColumnsError nêu rõ tên cột
def test_running_twice_is_idempotent() -> None: ...
```

- [ ] **Step 2:** Chạy, kỳ vọng FAIL.
- [ ] **Step 3:** Cài đặt. Trong `lifespan`: thiếu `GOOGLE_SERVICE_ACCOUNT_JSON` hoặc `SYSTEM_SPREADSHEET_ID` thì log cảnh báo và bỏ qua bootstrap (để `create_app()` trong test vẫn chạy). Thiếu `SESSION_SECRET` khi bootstrap chạy thật thì raise `ConfigError`. `GOOGLE_SERVICE_ACCOUNT_JSON` chấp nhận cả nội dung JSON lẫn đường dẫn file: bắt đầu bằng `{` thì là nội dung.
- [ ] **Step 4:** Chạy pytest, mypy, ruff. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(core): bootstrap system spreadsheet and first admin`.

---

### Task 8: Frontend: khung app, đăng nhập, trang quản lý user

**Files:**
- Create: toàn bộ `frontend/` theo cây ở trên.

**Interfaces:**
- Consumes: OpenAPI từ backend (`http://localhost:8000/openapi.json`).
- Produces:
  - `npm run gen:api` chạy `openapi-typescript http://localhost:8000/openapi.json -o lib/api/schema.d.ts`. File sinh ra được commit.
  - `lib/api/client.ts` tạo `api = createClient<paths>({ baseUrl: "" })` (openapi-fetch). Gặp 401 thì chuyển sang `/login`.
  - `useMe()` (TanStack Query) trả về `{ user, isLoading }`.
  - `lib/nav.ts` có `NAV_ITEMS: { href: string; labelKey: string; icon: LucideIcon; roles: Role[] }[]` và `visibleNavItems(role: Role)`.

- [ ] **Step 1:** `npx create-next-app@latest frontend --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*"`. Sau đó `npx shadcn@latest init` và `npx shadcn@latest add button input label select table dialog dropdown-menu badge card avatar switch sonner skeleton separator tooltip`. Cài `next-intl next-themes @tanstack/react-query openapi-fetch zod react-hook-form @hookform/resolvers lucide-react`, và dev: `openapi-typescript vitest @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react`. Ghi phiên bản Next.js vào `DECISIONS.md`.
- [ ] **Step 2:** `next.config.ts`: `output: "standalone"`, rewrites `/api/:path*` → `${process.env.API_INTERNAL_URL}/api/:path*`, bọc bằng plugin next-intl. `i18n/request.ts` cố định locale `vi`, đọc `messages/vi.json`, không có tiền tố locale trên URL.
- [ ] **Step 3: Test (Vitest)**

```ts
// lib/nav.test.ts
it("chỉ ADMIN thấy mục Người dùng", () => {
  expect(visibleNavItems("ADMIN").map(i => i.href)).toContain("/admin/users");
  expect(visibleNavItems("QA_LEAD").map(i => i.href)).not.toContain("/admin/users");
});
// components/users/user-form-schema.test.ts
it("báo lỗi email sai định dạng bằng tiếng Việt", () => {
  const result = userFormSchema.safeParse({ email: "abc", name: "An", role: "TESTER" });
  expect(result.success).toBe(false);
});
// messages/vi.test.ts
it("mọi key dùng trong NAV_ITEMS đều có trong vi.json", () => { ... });
```

- [ ] **Step 4:** `npm run test`. Kỳ vọng: FAIL (chưa có module).
- [ ] **Step 5:** Làm giao diện theo mục 11 của spec:
  - `/login`: thẻ ở giữa màn hình, logo chữ "AI Test Runner", nút "Đăng nhập bằng Google" dẫn tới `/api/auth/login`. Có `?error=not_allowed` thì hiện thông báo "Tài khoản của bạn chưa được cấp quyền. Hãy liên hệ Admin."
  - `(app)/layout.tsx`: sidebar bên trái (logo, mục menu theo `visibleNavItems`, khu vực "Dự án" để trống, ghi "Sẽ có ở M2"), topbar (avatar và tên, menu: chuyển giao diện sáng/tối, Đăng xuất). Đang tải thì hiện skeleton, không nháy nội dung.
  - `(app)/page.tsx`: "Tổng quan", màn hình trống thân thiện kèm câu hướng dẫn.
  - `/admin/users`: bảng (Email, Tên, Vai trò dạng badge màu, Trạng thái dạng switch, Ngày tạo), ô tìm kiếm, nút "Thêm người dùng" mở dialog form (react-hook-form + zod). Thành công hoặc lỗi thì hiện toast; lỗi 409/400 hiện đúng `detail` từ API. Người không phải Admin vào trang này thì thấy "Bạn không có quyền xem trang này".
- [ ] **Step 6:** `npm run test && npx tsc --noEmit && npm run lint && npm run build`. Kỳ vọng: tất cả PASS.
- [ ] **Step 7:** Commit `feat(frontend): add app shell, login and user management`.

---

### Task 9: Docker Compose, README, chạy thử toàn bộ

**Files:**
- Create: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `README.md`
- Modify: `DECISIONS.md`

**Interfaces:**
- `docker-compose.yml`:
  - `redis` (`redis:7-alpine`, `--appendonly yes`, volume `redis-data`).
  - `api` (build `./backend`, cổng `8000`, `env_file: .env`, `REDIS_URL=redis://redis:6379/0`).
  - `frontend` (build `./frontend`, cổng `3000`, `API_INTERNAL_URL=http://api:8000`).
  - Không mount thư mục của host.
- `backend/Dockerfile`: `python:3.13-slim`, cài bằng uv từ `uv.lock`, chạy `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Hàm `app` ở module level là `create_app()`.
- `frontend/Dockerfile`: nhiều stage, `node:24-alpine`, chạy bản standalone.

- [ ] **Step 1:** Viết hai Dockerfile và `docker-compose.yml`.
- [ ] **Step 2:** `docker compose up --build -d`, rồi `curl http://localhost:3000/api/health`. Kỳ vọng: `{"status":"ok"}` (đi qua proxy của frontend).
- [ ] **Step 3:** Viết `README.md` bằng tiếng Việt, gồm:
  1. Tổng quan: dự án giải quyết gì, ai dùng.
  2. Kiến trúc: sơ đồ ở mục 6 của spec.
  3. Cấu trúc thư mục.
  4. Chuẩn bị:
     - Tạo OAuth Client loại Web, redirect `http://localhost:3000/api/auth/callback`, consent screen ở chế độ Testing, thêm test user.
     - Tạo Service Account và tải key.
     - Tạo file Sheet hệ thống trống, share quyền Editor cho email service account, lấy ID.
     - GitHub App và Anthropic key: ghi "cần từ M2/M4".
  5. Điền `.env` từ `.env.example`.
  6. Chạy bằng Docker: `docker compose up --build`.
  7. Chạy để phát triển: `docker compose up redis`, rồi `cd backend && uv run uvicorn app.main:app --reload`, rồi `cd frontend && npm run dev`.
  8. Chạy test: backend `uv run pytest`, frontend `npm run test`.
  9. Gỡ lỗi thường gặp: `redirect_uri_mismatch`, service account chưa có quyền với Sheet, email chưa có trong tab `Users`.
- [ ] **Step 4: Chạy thử thật** (cần chủ dự án điền `.env` với Google thật):
  1. Mở `http://localhost:3000`, bị chuyển sang `/login`.
  2. Đăng nhập bằng email `BOOTSTRAP_ADMIN_EMAIL`, vào được trang Tổng quan.
  3. Sheet hệ thống đã có đủ 4 tab kèm header.
  4. Vào Người dùng, thêm một user, thấy dòng mới trong tab `Users` và một dòng trong `AuditLog`.
  5. Đăng nhập bằng email không có trong `Users`, thấy thông báo chưa được cấp quyền.

  Nếu chưa có `.env` thật thì ghi rõ bước này **chưa chạy** trong báo cáo, không được coi như đã xong.
- [ ] **Step 5:** `docker compose down`. Commit `chore: add Docker Compose setup and README`.

# AI Test Runner

Web app nội bộ giúp đội QA **viết test case theo chuẩn chung** và **chạy test tự động**: một worker mở app thật bằng Playwright, làm theo các bước tự động của từng case rồi ghi PASS/FAIL (kèm bước lỗi và ảnh chụp) vào Google Sheets. Sau này AI sẽ điền sẵn các bước tự động. Những case FAIL được QA Lead duyệt trước khi tạo thành GitHub Issue (M5).

> Trạng thái: **M1 — Nền tảng**, **M2 — Quản trị dự án** (dự án gắn repo GitHub và Google Sheet riêng, thành viên, màn hình, chia việc, trang Việc của tôi), **M3 — Test case** (viết, duyệt, báo xung đột khi lưu) và **M4 — Worker chạy test bằng Playwright** (xem mục "Chạy test tự động").
> Các mốc tiếp theo xem ở [tài liệu thiết kế](docs/superpowers/specs/2026-11-12-ai-test-runner-design.md), mục 15.

## Ai dùng

| Vai trò | Làm gì |
|---|---|
| Admin | Quản lý người dùng, tạo dự án, gắn repo GitHub và Google Sheet |
| QA Lead | Chia việc, duyệt test case, chạy test, duyệt kết quả và tạo issue |
| Tester | Viết test case cho màn hình được giao |
| Viewer | Chỉ xem |

## Kiến trúc

```
Trình duyệt
    │
[frontend: Next.js]  ── giao diện; mọi /api/* được chuyển tiếp sang api
    │
[api: FastAPI]  ── REST API, đăng nhập, phân quyền, nghiệp vụ
    │        │
    │      Redis  ── phiên đăng nhập, khoá khi ghi, cache, hàng đợi run
    │         │
    │   [worker: Python + Playwright]  ── chạy THẲNG trên máy có app cần test (không Docker)
    │
Google Sheets  ── nơi lưu dữ liệu (chỉ backend được ghi)
```

## Cấu trúc thư mục

```
├── backend/          # Python (FastAPI): app/api, app/core, tests
├── frontend/         # Next.js: app/, components/, lib/, messages/vi.json
├── docs/superpowers/ # tài liệu thiết kế (specs) và kế hoạch (plans)
├── docker-compose.yml
├── .env.example      # mẫu biến môi trường
└── DECISIONS.md      # các quyết định/giả định trong lúc làm
```

## Test case (M3)

- Mã case dạng `TC-000123`, đánh số theo từng dự án. Tester tạo case trên màn hình được giao cho mình.
- Quy trình: `DRAFT` → `IN_REVIEW` (gửi duyệt) → `APPROVED` (QA Lead duyệt). QA Lead cũng có thể **trả lại kèm nhận xét** (case về `DRAFT`, Tester thấy nhận xét ở đầu trang rồi sửa và gửi lại). Case không dùng nữa chuyển sang `DEPRECATED`; chỉ QA Lead/Admin **khôi phục** (về `DRAFT`).
- Trạng thái của việc được giao (trang "Việc của tôi") tự suy ra từ các case do Tester đó tạo trên màn hình đó, không phải nhập tay.
- **Báo xung đột (409)**: nếu thấy "Case này vừa được … cập nhật. Vui lòng tải lại." nghĩa là có người khác đã lưu case trước bạn. Bấm **Tải lại** để xem nội dung mới; phần bạn đang sửa sẽ mất, nên chép lại trước nếu cần. Việc duyệt, trả lại, ngừng dùng cũng bị kiểm tra như vậy.

## Chạy test tự động (M4)

- Mỗi bước của test case có phần **"Tự động"** (thu gọn mặc định): chọn hành động (mở trang, nhập chữ, bấm, chọn, thấy chữ, không thấy chữ, URL là), tìm phần tử bằng **chữ hiển thị** hoặc **nhãn của ô** (CSS selector để ở mục "Nâng cao"), và giá trị. Case không có phần tự động nào thì worker ghi **BLOCKED** ("Chưa có bước tự động"); thiếu một bước giữa chừng cũng BLOCKED, không chạy nửa chừng.
- Tab **Chạy test** của dự án: QA Lead/Admin chọn phạm vi, thấy số case sẽ chạy rồi bấm **Chạy**; ai xem được dự án đều xem được tiến độ, kết quả, lý do, bước lỗi và ảnh chụp. Mỗi dự án chỉ có một lần chạy một lúc.
- PASS/FAIL do Playwright quyết định. Lỗi của chính worker (trình duyệt sập, quá giờ) ghi **INCONCLUSIVE**, không tính là FAIL.
- Chưa có thông báo cho các role: người dùng tự mở tab Chạy test để xem.

### Chạy worker (làm trên máy có app cần test)

Worker **không chạy trong Docker**, vì cần mở `localhost` của chính máy bạn.

```bash
# 1. Redis phải đang chạy (worker và api dùng chung hàng đợi)
docker compose up -d redis

# 2. Cài một lần: thư viện và trình duyệt Chromium cho Playwright
cd backend
uv sync
uv run playwright install chromium

# 3. Khai báo app cần test (một lần cho mỗi dự án)
cd ..
cp worker-projects.example.json worker-projects.json   # rồi sửa theo app của bạn

# 4. Chạy worker (dừng bằng Ctrl+C)
cd backend
uv run python -m app.worker
```

`worker-projects.json` nằm ở thư mục gốc repo, **đã được gitignore** vì chứa mật khẩu tài khoản test. Mỗi dự án (theo mã `PRJ-0001`...) khai báo: `app_path` (thư mục code của app), `start_command` (ví dụ `npm run dev`), `app_url`, tài khoản test và `login_steps` (các bước đăng nhập, dùng `{email}` và `{password}`). Mỗi lần chạy, worker tự bật app, đăng nhập một lần, chạy từng case rồi tắt cả app. Không có API nào sửa được file này, nên người dùng web không đổi được lệnh chạy trên máy bạn.

Ảnh chụp lỗi lưu ở `artifacts/<mã dự án>/<mã run>/<mã case>.png` (gitignore). Nếu worker bị tắt giữa lúc đang chạy, lần khởi động sau sẽ đánh dấu run đó là **FAILED** ("Worker bị dừng giữa chừng") để dự án chạy lại được.

## Chuẩn bị (làm một lần)

Cần: **Docker Desktop**. Nếu muốn chạy từng phần để phát triển thì cần thêm **Python 3.12+**, **[uv](https://docs.astral.sh/uv/)** và **Node 24**.

### 1. Google OAuth (để đăng nhập)
1. Vào [Google Cloud Console](https://console.cloud.google.com/), tạo (hoặc chọn) một project.
2. **APIs & Services → OAuth consent screen**: chọn **External**, để ở chế độ **Testing**. Ở mục **Test users**, thêm email của những người sẽ dùng app (tối đa 100).
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:3000/api/auth/callback`
4. Chép **Client ID** và **Client secret** vào `.env`.

### 2. Service Account (để backend đọc/ghi Google Sheets)
1. **APIs & Services → Library**: bật **Google Sheets API**.
2. **IAM & Admin → Service Accounts → Create service account**. Không cần gán role.
3. Vào service account vừa tạo, chọn **Keys → Add key → JSON**, rồi tải file key về. **Không commit file này.**
4. Ghi lại email của service account (dạng `ten@project.iam.gserviceaccount.com`).

### 3. File Google Sheet hệ thống
1. Tạo một Google Sheet **trống**.
2. **Share** file cho email service account với quyền **Editor**. Những người khác chỉ nên được quyền **Viewer**.
3. Lấy **Spreadsheet ID** từ đường link: `https://docs.google.com/spreadsheets/d/<ID>/edit`.
4. Khi app khởi động lần đầu, nó tự tạo các tab `Users`, `Projects`, `ProjectMembers`, `AuditLog`, và thêm Admin đầu tiên.

### 4. GitHub App (để chọn repo khi tạo dự án)
GitHub App là một "tài khoản robot" chỉ được cài vào đúng các repo cần test, với đúng các quyền cần dùng. Nhờ vậy app không phải dùng token cá nhân của ai.

1. Vào **Settings** của organization (ví dụ `Cross-Players`) → **Developer settings → GitHub Apps → New GitHub App**.
   - GitHub App name: tên bất kỳ, ví dụ `ai-test-runner-cross-players`.
   - Homepage URL: `http://localhost:3000`.
   - **Webhook**: bỏ chọn **Active** (app chưa cần nhận sự kiện).
   - **Repository permissions**: `Contents` → *Read-only*, `Issues` → *Read and write*, `Metadata` → *Read-only* (thường đã tự chọn).
   - Where can this GitHub App be installed: **Only on this account**.
2. Bấm **Create GitHub App**. Ghi lại **App ID** ở đầu trang.
3. Kéo xuống mục **Private keys** → **Generate a private key**. Máy sẽ tải về một file `.pem`. **Không commit file này.**
4. Ở menu trái, chọn **Install App** → **Install** → **Only select repositories** → chọn các repo cần test.
5. Điền vào `.env`:
   - `GITHUB_APP_ID`: App ID ở bước 2.
   - `GITHUB_APP_PRIVATE_KEY`: nội dung file `.pem`, viết trên **một dòng** (xuống dòng thay bằng `
`) và đặt trong dấu nháy đơn. Lệnh sau in ra đúng dạng đó, bạn chỉ việc copy dán:
     ```bash
     cd backend
     uv run python -m app.tools.pem_to_env duong-dan/toi/file.pem
     ```

### 5. File Google Sheet cho mỗi dự án
Mỗi dự án cần một file Google Sheet **trống** riêng. Tạo file, **share quyền Editor** cho email service account (trang tạo dự án có hiện sẵn email này kèm nút sao chép), rồi dán link vào ô "Link hoặc ID Google Sheet". App tự tạo 7 tab: `Meta`, `Screens`, `Assignments`, `TestCases`, `Runs`, `Results`, `AuditLog`.

### 6. Anthropic key
Chưa cần. M4 chạy test bằng Playwright, không dùng AI. Key chỉ cần khi sau này AI điền sẵn các bước tự động.

## Điền `.env`

```bash
cp .env.example .env
```

| Biến | Điền gì |
|---|---|
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Ở bước 1 |
| `SESSION_SECRET` | Một chuỗi ngẫu nhiên dài, ví dụ kết quả của `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `BOOTSTRAP_ADMIN_EMAIL` | Email Google của bạn, sẽ thành Admin đầu tiên |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Nội dung file key JSON (viết trên một dòng), hoặc đường dẫn tới file key |
| `SYSTEM_SPREADSHEET_ID` | Ở bước 3 |
| `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` | Ở bước 4 |

> Khi chạy bằng Docker, nên dán **nội dung** JSON (một dòng) vào `GOOGLE_SERVICE_ACCOUNT_JSON`, vì container không thấy file trên máy bạn.

## Chạy bằng Docker (cách đơn giản nhất)

```bash
docker compose up --build
```

- Mở http://localhost:3000, đăng nhập bằng email `BOOTSTRAP_ADMIN_EMAIL`.
- Kiểm tra API còn sống: http://localhost:3000/api/health trả về `{"status":"ok"}`.
- Tắt: `docker compose down`. Thêm `-v` nếu muốn xoá luôn dữ liệu Redis (mọi phiên đăng nhập).

## Chạy từng phần (khi phát triển)

```bash
# 1. Redis
docker compose up -d redis

# 2. Backend (cổng 8000, tự nạp lại khi sửa code)
cd backend
uv sync
uv run uvicorn app.main:create_app --factory --reload --port 8000

# 3. Frontend (cổng 3000), ở một terminal khác
cd frontend
npm install
npm run dev
```

Backend tự đọc file `.env` ở thư mục gốc repo, dùng chung với Docker. Khi chạy từng phần, trong `.env` dùng `REDIS_URL=redis://localhost:6379/0`. Docker tự đổi giá trị này thành `redis://redis:6379/0`.

## Chạy test và kiểm tra code

```bash
# Backend
cd backend
uv run pytest            # test
uv run mypy app tests    # kiểm tra kiểu (strict)
uv run ruff check .      # kiểm tra cách viết code

# Frontend
cd frontend
npm run test             # Vitest
npm run typecheck        # TypeScript
npm run lint             # ESLint
```

Khi sửa API ở backend, chạy `npm run gen:api` trong `frontend/` để sinh lại kiểu TypeScript từ OpenAPI.

## Gỡ lỗi thường gặp

| Hiện tượng | Nguyên nhân và cách sửa |
|---|---|
| Google báo `redirect_uri_mismatch` | Redirect URI ở bước 1 phải đúng `http://localhost:3000/api/auth/callback` |
| Google báo app chưa được xác minh, hoặc chặn đăng nhập | Email chưa có trong **Test users** của OAuth consent screen |
| Đăng nhập xong bị đưa về `/login?error=not_allowed` | Email chưa có trong tab `Users`, hoặc cột `active` đang là `FALSE` |
| API trả 503 "chưa được cấu hình Google Sheets" | Thiếu `GOOGLE_SERVICE_ACCOUNT_JSON` hoặc `SYSTEM_SPREADSHEET_ID` |
| Backend báo lỗi 403 / `PERMISSION_DENIED` khi khởi động | Chưa share file Sheet cho email service account với quyền Editor |
| Backend báo `Tab 'Users' thiếu cột: ...` | Ai đó đã sửa hàng tiêu đề trong Sheet; thêm lại đúng tên cột bị thiếu |
| Backend dừng với `Thiếu SESSION_SECRET` | Điền `SESSION_SECRET` trong `.env` |
| Trang tạo dự án báo "Chưa cấu hình GitHub App" | Thiếu `GITHUB_APP_ID` hoặc `GITHUB_APP_PRIVATE_KEY`; chạy lại `docker compose up -d` sau khi điền |
| Tạo dự án báo "GitHub trả lỗi 401" | Private key sai định dạng: phải là một dòng, có `
`, trong dấu nháy đơn |
| Không thấy repo trong danh sách | GitHub App chưa được cài vào repo đó (Install App → chọn thêm repo) |
| Tạo dự án báo "App chưa có quyền ghi vào Sheet này" | Share file Sheet của dự án quyền Editor cho email service account |

## Quy ước làm việc

- **Gitflow**: làm trên nhánh `feature/*` tách từ `develop`, rồi tạo Pull Request vào `develop`. Không commit thẳng lên `main`.
- **Commit**: theo Conventional Commits, phần mô tả viết tiếng Việt có dấu. Ví dụ `feat(core): thêm khoá Redis`.
- Mọi đọc/ghi Google Sheets đều đi qua `backend/app/core/repositories`. Mọi API đều kiểm tra quyền ở backend.

# Hướng dẫn cài đặt và sử dụng

File này gồm hai phần:
- **Phần A (Trang 1–6):** Dành cho admin/người deploy — cài đặt toàn bộ hệ thống từ đầu.
- **Phần B (cuối file):** Dành cho Tester/QA Lead — bắt đầu dùng app sau khi admin đã cài xong.

---

# Phần A — Cài đặt từ đầu (dành cho admin)

Dành cho người tiếp nhận dự án và muốn tự cấu hình mọi thứ dưới tài khoản của mình. Mỗi bước đều giải thích *tại sao* cần làm — không chỉ làm gì.

---

## Trước khi bắt đầu

Bạn cần có:
- Tài khoản Google (Gmail)
- Tài khoản GitHub (cá nhân hoặc organization)
- Docker Desktop đã cài ([tải tại đây](https://www.docker.com/products/docker-desktop/))

Toàn bộ cài đặt bên dưới làm **một lần duy nhất**. Sau đó chỉ cần `docker compose up` là app chạy.

---

## Phần 1 — Google Cloud

> **Tại sao cần Google Cloud?**
> App dùng Google theo hai cách: (1) để người dùng đăng nhập bằng tài khoản Google thay vì phải tạo mật khẩu riêng, và (2) để đọc/ghi Google Sheets làm cơ sở dữ liệu. Cả hai đều cần bạn đăng ký một "project" trên Google Cloud Console.

### 1.1 Tạo project Google Cloud

1. Vào [https://console.cloud.google.com](https://console.cloud.google.com), đăng nhập bằng Gmail của bạn.
2. Bấm vào menu project ở trên cùng → **New Project**.
3. Đặt tên dễ nhớ, ví dụ `ai-test-runner`. Bấm **Create**.

> Project này là "không gian" quản lý mọi thứ liên quan đến Google cho app. Nó nằm dưới tài khoản Gmail của bạn — bạn là chủ, không ai khác bị tính phí.

### 1.2 Bật Google Sheets API

1. Trong project vừa tạo, vào **APIs & Services → Library**.
2. Tìm **Google Sheets API**, bấm vào, chọn **Enable**.

> Mặc định Google Cloud chặn tất cả API. Phải bật thủ công thì backend mới được phép đọc/ghi Sheets.

### 1.3 Cài đặt màn hình đăng nhập (OAuth Consent Screen)

> **Tại sao?** Khi người dùng bấm "Đăng nhập bằng Google", Google sẽ hiện một màn hình xin quyền. Màn hình đó cần được cấu hình trước.

1. Vào **APIs & Services → OAuth consent screen**.
2. Chọn **External** (dùng được cho mọi Gmail), bấm **Create**.
3. Điền thông tin:
   - App name: `AI Test Runner`
   - User support email: Gmail của bạn
   - Developer contact: Gmail của bạn
4. Bấm **Save and Continue** qua các bước tiếp theo (không cần thêm scope hay domain).
5. Ở bước **Test users**: thêm Gmail của **tất cả người sẽ dùng app** (kể cả Gmail của bạn).

> **Quan trọng:** Khi app đang ở chế độ "Testing" (chưa publish), chỉ những Gmail trong danh sách Test users mới qua được bước đăng nhập Google. Gmail nào không có trong danh sách sẽ bị Google chặn ngay, không vào được app. Thêm người mới = thêm Gmail của họ vào đây.

### 1.4 Tạo OAuth Client ID (cho đăng nhập)

1. Vào **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Chọn **Web application**.
3. Ở mục **Authorized redirect URIs**, bấm **Add URI** và điền:
   ```
   http://localhost:3000/api/auth/callback
   ```
   (Nếu sau này deploy lên server thật thì thêm URI của server vào đây.)
4. Bấm **Create**. Cửa sổ hiện **Client ID** và **Client Secret** — lưu lại ngay, dùng ở bước `.env`.

> Client ID/Secret là "chìa khóa" để app chứng minh với Google rằng request đăng nhập đến từ đúng app này, không phải ai khác giả mạo.

### 1.5 Tạo Service Account (để backend đọc/ghi Sheets)

> **Tại sao dùng Service Account thay vì đăng nhập bằng người?** Vì backend cần đọc/ghi Sheets tự động, không có người ngồi nhấp "Cho phép" mỗi lần. Service Account là "tài khoản robot" của Google, dùng file key thay vì mật khẩu.

1. Vào **IAM & Admin → Service Accounts → Create Service Account**.
2. Đặt tên, ví dụ `sheets-backend`. Bấm **Create and Continue**.
3. Bỏ qua phần gán role, bấm **Done**.
4. Bấm vào service account vừa tạo → tab **Keys** → **Add Key → Create new key → JSON**.
5. File `.json` sẽ được tải về máy. **Giữ file này an toàn, không commit lên Git.**
6. Ghi lại **email của service account** (trông giống `sheets-backend@ai-test-runner.iam.gserviceaccount.com`). Bạn sẽ cần email này khi share Google Sheet.

---

## Phần 2 — Google Sheets

### 2.1 Sheet hệ thống (lưu Users, Projects, Members)

> **Tại sao?** App dùng Google Sheets làm cơ sở dữ liệu. Sheet hệ thống chứa danh sách người dùng và thông tin chung.

1. Mở [https://sheets.google.com](https://sheets.google.com), tạo một sheet mới **để trống**.
2. Đặt tên dễ nhận ra, ví dụ `AI Test Runner — System`.
3. Bấm **Share**, dán **email của service account** (từ bước 1.5), chọn quyền **Editor**, bỏ chọn "Notify people", bấm **Share**.
4. Lấy **Spreadsheet ID** từ link trình duyệt:
   ```
   https://docs.google.com/spreadsheets/d/[ĐÂY LÀ ID CỦA BẠN]/edit
   ```
5. Ghi lại ID này, dùng ở bước `.env`.

> Khi app khởi động lần đầu, nó tự tạo các tab `Users`, `Projects`, `ProjectMembers`, `AuditLog` và thêm Admin đầu tiên (email `BOOTSTRAP_ADMIN_EMAIL` trong `.env`).

### 2.2 Sheet cho từng dự án

> Mỗi dự án cần một Sheet riêng. Làm bước này sau khi app đã chạy, khi bạn tạo dự án mới trong app:
> 1. Tạo một Google Sheet trống.
> 2. Share quyền **Editor** cho email service account (trang tạo dự án trong app có nút sao chép email này).
> 3. Dán link Sheet vào ô "Link hoặc ID Google Sheet" khi tạo dự án.

---

## Phần 3 — GitHub App

> **Tại sao cần GitHub App?** Khi QA Lead duyệt một test case, app tự động tạo Issue trong repo GitHub của dự án. Để làm vậy, app cần quyền ghi Issue — nhưng không nên dùng token cá nhân của ai. GitHub App là "tài khoản robot" chỉ được cài vào đúng các repo cần thiết, với đúng quyền cần dùng.

1. Vào **Settings** của tài khoản/organization trên GitHub → **Developer settings → GitHub Apps → New GitHub App**.
2. Điền:
   - **GitHub App name**: tên bất kỳ, ví dụ `ai-test-runner`
   - **Homepage URL**: `http://localhost:3000`
   - **Webhook**: bỏ chọn **Active**
3. Ở mục **Repository permissions**, đặt:
   - `Contents` → **Read-only**
   - `Issues` → **Read and write**
   - `Metadata` → **Read-only** (thường tự chọn)
4. **Where can this GitHub App be installed**: chọn **Only on this account**.
5. Bấm **Create GitHub App**. Ghi lại **App ID** ở đầu trang.
6. Kéo xuống mục **Private keys** → **Generate a private key**. File `.pem` được tải về. **Không commit file này.**
7. Ở menu trái chọn **Install App → Install → Only select repositories** → chọn repo của dự án.

### Chuyển file `.pem` thành dạng dùng được trong `.env`

File `.pem` có nhiều dòng, không thể dán thẳng vào `.env`. Chạy lệnh này để chuyển sang một dòng:

```bash
cd backend
uv run python -m app.tools.pem_to_env duong-dan/toi/file.pem
```

Copy kết quả dán vào `GITHUB_APP_PRIVATE_KEY` trong `.env`.

---

## Phần 4 — Điền file `.env`

```bash
cp .env.example .env
```

Mở file `.env` và điền:

| Biến | Lấy từ đâu | Dùng để làm gì |
|---|---|---|
| `GOOGLE_CLIENT_ID` | Bước 1.4 | Xác thực người dùng đăng nhập |
| `GOOGLE_CLIENT_SECRET` | Bước 1.4 | Xác thực người dùng đăng nhập |
| `SESSION_SECRET` | Tự tạo (xem bên dưới) | Mã hóa cookie phiên đăng nhập |
| `BOOTSTRAP_ADMIN_EMAIL` | Gmail của bạn | App thêm email này làm Admin đầu tiên khi khởi động |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Nội dung file `.json` ở bước 1.5 | Backend đọc/ghi Google Sheets |
| `SYSTEM_SPREADSHEET_ID` | Bước 2.1 | Trỏ vào Sheet hệ thống |
| `GITHUB_APP_ID` | Bước 3 | App ID của GitHub App |
| `GITHUB_APP_PRIVATE_KEY` | Bước 3 (đã chuyển sang một dòng) | Ký request tới GitHub |
| `AGENT_API_TOKEN` | Tự tạo (xem bên dưới) | Codex dùng token này khi gọi API ghi kết quả test |

**Tạo `SESSION_SECRET`:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Tạo `AGENT_API_TOKEN`** (tương tự):
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**Điền `GOOGLE_SERVICE_ACCOUNT_JSON`:** Dán **nội dung** file `.json` lên một dòng duy nhất (nếu dùng Docker), hoặc điền đường dẫn tới file nếu chạy từng phần khi phát triển.

---

## Phần 5 — Codex (AI chạy test)

> **Tại sao cần `AGENT_API_TOKEN`?** Codex chạy *ngoài* app. Sau khi chạy Playwright xong, nó cần gọi API của app để ghi kết quả vào Sheet. Token này là "mật khẩu" để Codex chứng minh nó được phép làm việc đó. Giữ token này ngoài Git và chỉ truyền qua biến môi trường.

### Token nào dùng chung, token nào mỗi người tự có?

Codex cần hai token khác nhau với mục đích khác nhau:

| Token | Dùng để làm gì | Mỗi người cần riêng? |
|---|---|---|
| `AGENT_API_TOKEN` | Gọi API của app để ghi kết quả vào Sheet | **Không** — cả nhóm dùng chung một giá trị duy nhất; admin gửi riêng qua tin nhắn bảo mật |
| `GITHUB_PAT_TOKEN` | Đọc Issue và comment kết quả lên GitHub | **Có** — mỗi người tạo token GitHub của riêng mình (xem bên dưới) |

> **Không copy nguyên file `.env` cho nhau.** File `.env` chứa Service Account key, OAuth secret, session secret — ai có những thứ này có thể đọc/ghi toàn bộ dữ liệu hoặc giả mạo đăng nhập. Chỉ chia sẻ đúng giá trị `AGENT_API_TOKEN` qua kênh bảo mật (Zalo, email nội bộ...).

### Tạo `GITHUB_PAT_TOKEN` cá nhân

Mỗi người dùng Codex tự tạo một lần trên tài khoản GitHub của mình:

1. Vào GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
2. Đặt tên dễ nhớ, ví dụ `codex-ai-test-runner`.
3. Ở **Repository access**: chọn **Only select repositories** → chọn repo của dự án.
4. Ở **Permissions**: `Issues` → **Read and write**. (Nếu repo riêng tư, thêm `Contents` → **Read-only**.)
5. Bấm **Generate token**, copy giá trị, lưu vào biến môi trường `GITHUB_PAT_TOKEN` trước khi mở Codex — **không dán vào file hay tin nhắn**.

Hướng dẫn cấu hình Codex và chạy test: xem [docs/codex-agent.md](docs/codex-agent.md).

---

## Phần 6 — Khởi động app

```bash
docker compose up --build
```

- Mở trình duyệt vào `http://localhost:3000`.
- Đăng nhập bằng Gmail đã điền vào `BOOTSTRAP_ADMIN_EMAIL`.
- Kiểm tra API còn sống: `http://localhost:3000/api/health` phải trả `{"status":"ok"}`.

Lần đầu khởi động, app tự tạo các tab trong Sheet hệ thống và thêm Admin đầu tiên.

---

## Thêm người dùng mới

Có **hai bước**, thiếu một là người đó không vào được:

| Bước | Làm ở đâu | Tại sao |
|---|---|---|
| 1. Thêm Gmail vào Test users | Google Cloud Console → OAuth consent screen → Test users | Google cần biết Gmail đó được phép qua bước xác thực |
| 2. Thêm vào tab Users của Sheet | App: trang Admin → Người dùng | App kiểm tra email có trong tab Users không trước khi cho vào |

> Khi nào cần thêm vào Google Cloud: **chỉ khi app vẫn ở chế độ "Testing"** (chưa publish). Nếu sau này publish app lên Production, bước 1 không cần nữa — chỉ cần bước 2.

---

## Chuyển giao cho người khác

Nếu bạn muốn chuyển toàn bộ cho người khác quản lý Google Cloud:

1. Vào Google Cloud Console → **IAM & Admin → IAM** → **Grant Access** → thêm Gmail của người tiếp nhận, chọn role **Owner**.
2. Người tiếp nhận vào Google Cloud, đổi project, tạo key mới cho Service Account (key cũ của bạn vẫn dùng được, nhưng nên thu hồi sau khi bàn giao xong).
3. Cập nhật `.env` với key mới.

---

## Lỗi thường gặp khi setup

| Lỗi | Nguyên nhân |
|---|---|
| Google báo "app chưa được xác minh" hoặc chặn đăng nhập | Gmail chưa có trong **Test users** (Phần 1.3) |
| Đăng nhập xong bị về `/login?error=not_allowed` | Gmail chưa có trong tab **Users** của Sheet hệ thống |
| `redirect_uri_mismatch` | URI ở bước 1.4 phải khớp chính xác với `http://localhost:3000/api/auth/callback` |
| Backend báo 403 / `PERMISSION_DENIED` lúc khởi động | Chưa share Sheet cho email service account với quyền **Editor** |
| "Chưa cấu hình GitHub App" | `GITHUB_APP_ID` hoặc `GITHUB_APP_PRIVATE_KEY` còn trống trong `.env` |
| "GitHub trả lỗi 401" | Private key sai định dạng — phải một dòng, có `\n`, trong dấu nháy đơn |

---

---

# Phần B — Hướng dẫn cho Tester / QA Lead

Bạn không cần cài đặt gì cả. Admin đã lo toàn bộ phần kỹ thuật. Bạn chỉ cần một Gmail và được admin thêm vào hệ thống.

---

## Bước 0 — Nhờ admin thêm bạn vào

Trước khi làm bất cứ điều gì, nhắn cho admin Gmail của bạn. Admin cần làm **hai việc**:

1. Thêm Gmail của bạn vào danh sách cho phép đăng nhập trên Google Cloud
2. Thêm bạn vào tab Users trong hệ thống, gán đúng vai trò (Tester, QA Lead, hay Viewer)

Thiếu một trong hai là bạn không vào được — xem mục "Lỗi thường gặp" ở cuối.

---

## Bước 1 — Đăng nhập

1. Mở trình duyệt, vào địa chỉ app (admin cho bạn địa chỉ này).
2. Bấm **Đăng nhập bằng Google**.
3. Chọn đúng Gmail mà bạn đã báo cho admin.

Nếu đăng nhập thành công, bạn sẽ thấy trang chính của app tương ứng với vai trò của mình.

---

## Bước 2 — Hiểu vai trò của bạn

| Vai trò | Làm được gì |
|---|---|
| **Tester** | Viết test case cho màn hình được giao, gửi lên duyệt |
| **QA Lead** | Chia việc cho Tester, duyệt hoặc trả lại test case, đồng bộ issue GitHub, xem kết quả chạy test |
| **Viewer** | Chỉ xem, không sửa được gì |
| **Admin** | Quản lý người dùng, dự án, cấu hình GitHub và Google Sheet |

---

## Luồng làm việc — Tester

### 1. Xem việc được giao

Vào **Việc của tôi** → tab **Đang làm** để thấy danh sách màn hình QA Lead đã giao cho bạn.

### 2. Viết test case

1. Bấm vào màn hình được giao.
2. Bấm **Thêm test case**.
3. Điền tên, mô tả và các bước thực hiện.
4. Lưu — case mới ở trạng thái `DRAFT`.

### 3. Gửi lên duyệt

Khi đã viết xong, bấm **Gửi duyệt** — case chuyển sang `IN_REVIEW`. QA Lead sẽ duyệt hoặc trả lại.

### 4. Nếu bị trả lại

Case về lại `DRAFT`, bạn thấy nhận xét của QA Lead ở đầu trang. Sửa theo nhận xét rồi **Gửi duyệt** lại.

> **Lưu ý khi có người cùng sửa:** Nếu thấy thông báo "Case này vừa được cập nhật. Vui lòng tải lại." — nghĩa là có người khác lưu trước bạn. Chép lại phần bạn đang sửa, bấm **Tải lại**, rồi điền lại.

---

## Luồng làm việc — QA Lead

### 1. Chia việc cho Tester

Vào dự án → **Phân công** → chọn Tester và màn hình cần viết case.

### 2. Duyệt test case

Vào **Việc của tôi** → tab **Đang làm** hoặc vào thẳng màn hình → chọn case đang `IN_REVIEW`:
- **Duyệt** → case chuyển sang `APPROVED`, app tự tạo GitHub Issue.
- **Trả lại** → điền nhận xét, case về `DRAFT`, Tester nhận thông báo.

### 3. Đồng bộ issue GitHub

Nếu bạn sửa case sau khi đã duyệt, nội dung issue trên GitHub có thể cũ. Bấm **Đồng bộ lại issue** trên trang test case để cập nhật.

### 4. Xem kết quả chạy test

Vào **Kết quả** trong dự án để xem từng lần Codex chạy: case nào PASS, FAIL, hay BLOCKED.

---

## Thông báo

Chuông 🔔 trên thanh đầu trang hiện số thông báo chưa đọc. Bạn nhận thông báo khi:
- Case của bạn được duyệt hoặc bị trả lại (Tester)
- Codex đã chạy xong một lần test (QA Lead)

---

## Lỗi thường gặp khi dùng app

| Hiện tượng | Cách xử lý |
|---|---|
| Google chặn đăng nhập, báo app chưa xác minh | Nhắn admin thêm Gmail của bạn vào Google Cloud Test users |
| Đăng nhập xong bị về trang lỗi "không được phép" | Nhắn admin thêm bạn vào tab Users và kiểm tra cột `active` |
| Không thấy dự án nào | Admin chưa thêm bạn vào dự án với vai trò phù hợp |
| Không thấy màn hình nào trong "Việc của tôi" | QA Lead chưa phân công màn hình cho bạn |
| Bấm "Gửi duyệt" nhưng không được | Kiểm tra case có đủ bước chưa; vai trò của bạn phải là Tester hoặc cao hơn |

# Thiết kế — AI Test Runner

> Ngày: 2026-11-12 · Repo: `Cross-Players/ai-test-runner`
> Tài liệu này dựa trên PRD gốc của team và các quyết định đã chốt trong buổi trao đổi. Mỗi quyết định đều ghi rõ nguồn: **[Chủ dự án]** là người dùng đã nói, **[Đề xuất]** là quyết định của người viết thiết kế, chủ dự án có thể sửa.
> Tài liệu tự đủ để lập kế hoạch, không cần đọc PRD gốc.

---

## 1. Mục đích và lý do

Team tester đã viết nhiều test case, nhưng việc chạy test và ghi nhận lỗi vẫn làm tay, tốn thời gian và khó theo dõi. Cần một **web app nội bộ** để:

1. Tester nhập test case có cấu trúc, chia theo từng màn hình/chức năng.
2. Admin và QA Lead chia việc và gắn dự án với repo GitHub.
3. AI đọc source code của app cần test để đối chiếu với từng test case và kết luận PASS/FAIL.
4. Kết quả được ghi vào Google Sheets. Lỗi chỉ thành GitHub Issue **sau khi QA Lead duyệt**.

**Thành công nghĩa là:** test case của cả team được viết theo một chuẩn chung, nhiều tester làm song song mà không mất dữ liệu của nhau, và QA Lead bấm một nút là có kết quả AI review kèm bằng chứng, rồi từ đó tạo issue sạch, không trùng.

## 2. Mục tiêu, không phải mục tiêu, điều cần tránh

**Mục tiêu (giai đoạn 1 / MVP)**
- Đăng nhập Google và phân quyền theo 4 vai trò.
- Quản lý dự án; chọn repo và branch qua GitHub App.
- Màn hình/chức năng, chia việc, trang "Việc của tôi".
- CRUD test case, gửi duyệt, duyệt.
- AI **review tĩnh**: đọc source code, đối chiếu với test case.
- Màn hình kết quả; tạo issue hoặc comment vào issue cũ, có chống trùng.
- Dashboard cơ bản.
- Toàn bộ dữ liệu nằm trên Google Sheets.

**Không phải mục tiêu của giai đoạn 1** (để sang giai đoạn 2)
- AI bấm thử app thật bằng Playwright, chụp màn hình hoặc quay video làm bằng chứng. **[Chủ dự án]** xác nhận hiện chưa có staging, nhưng có source của các app.
- Lịch chạy định kỳ; tự đóng issue khi case pass lại; dashboard nâng cao.
- AI tự build và chạy app từ source (cần sandbox, chưa làm).
- Hỗ trợ test app mobile.

**Điều cần tránh** (dù có chạy được vẫn coi là thất bại)
- Hai người sửa cùng một test case mà một bên **bị ghi đè mất công không hay biết**.
- Issue rác hoặc issue trùng trên GitHub làm dev mất niềm tin vào hệ thống.
- Source code của repo được test lọt vào log, vào Sheet hoặc xuống trình duyệt.
- Secret (token GitHub, key Google, key Anthropic) lọt xuống trình duyệt.
- Giao diện rối, khó dùng. **[Chủ dự án]:** "giao diện phải đẹp, dễ nhìn, dễ dùng".

## 3. Ràng buộc đã chốt

| Ràng buộc | Nguồn |
|---|---|
| App dùng nội bộ, quy mô nhỏ (một team QA) | [Chủ dự án] |
| **Google Sheets là nơi lưu dữ liệu chính.** Người có quyền thì được mở Sheet để xem; chỉ backend được ghi | [Chủ dự án] |
| **Backend viết bằng Python** | [Chủ dự án] |
| Hai người cùng sửa một case: người lưu sau nhận thông báo "vui lòng tải lại". Tạm thời không cần so sánh hay gộp nội dung | [Chủ dự án] |
| Chưa có staging. Giai đoạn 1 chỉ review tĩnh từ source | [Chủ dự án] |
| Giao diện đẹp, dễ nhìn, dễ dùng; ngôn ngữ tiếng Việt | [Chủ dự án] + PRD |
| GitHub: dùng GitHub App, không dùng token cá nhân | PRD |
| AI: Claude (Anthropic) | PRD |
| QA Lead duyệt trước khi tạo issue, không tự động tạo | PRD; [Đề xuất] giữ nguyên |
| **Mỗi app cần test nằm trong một repo** (frontend và backend có thể là các thư mục trong cùng repo đó) | [Chủ dự án] |
| Quy mô: 10–20 người dùng, khá nhiều test case. Chưa xin Google tăng giới hạn | [Chủ dự án] |
| **Trước mắt chạy local bằng Docker Compose.** Chưa có server hay domain | [Chủ dự án] |
| Dự án chia rõ hai phần `frontend/` và `backend/` | [Chủ dự án] |
| Có `README.md` ở thư mục gốc: tổng quan dự án và cách chạy | [Chủ dự án] |
| Không làm bản chạy thử AI riêng. Chủ dự án sẽ thử bằng chính app sau khi làm xong | [Chủ dự án] |

## 4. Người dùng và phân quyền

| Quyền | Admin | QA Lead | Tester | Viewer |
|---|:-:|:-:|:-:|:-:|
| Quản lý user, gán vai trò | ✅ | | | |
| Tạo dự án, chọn repo/branch/Sheet | ✅ | | | |
| Thêm thành viên vào dự án | ✅ | ✅ | | |
| Tạo màn hình, chia việc | ✅ | ✅ | | |
| Tạo / sửa test case | ✅ | ✅ | ✅ (case mình tạo, hoặc case thuộc màn hình được giao) | |
| Duyệt test case | ✅ | ✅ | | |
| Kích hoạt chạy test | ✅ | ✅ | | |
| Duyệt kết quả, tạo GitHub Issue | ✅ | ✅ | | |
| Xem dự án, case, kết quả | ✅ | ✅ | ✅ (dự án mình là thành viên) | ✅ (dự án mình là thành viên) |

- Vai trò là **toàn hệ thống**, gán trong tab `Users`. Mỗi user chỉ thấy các dự án mình là thành viên; riêng Admin thấy tất cả.
- QA Lead chỉ thao tác được trên dự án mình là thành viên. **[Đề xuất]**
- Quyền **bắt buộc kiểm tra ở backend (FastAPI)**. Frontend chỉ ẩn/hiện nút.

## 5. Luồng chính

```
Admin   : tạo dự án → chọn repo + branch → gắn Google Sheet → thêm thành viên
QA Lead : tạo danh sách màn hình → giao màn hình cho tester (kèm deadline)
Tester  : "Việc của tôi" → viết test case → gửi duyệt
QA Lead : duyệt test case → bấm chạy test (cả dự án / theo màn hình / lọc priority, severity)
Worker  : clone repo (chỉ đọc) → AI review từng case → ghi kết quả gộp vào Sheet
QA Lead : xem kết quả → chọn case FAIL → xem trước, sửa nội dung issue → tạo issue (hoặc comment vào issue cũ)
```

## 6. Kiến trúc

```
Trình duyệt
    │
[web: Next.js]  ── chỉ giao diện; mọi lời gọi /api/* được proxy sang api
    │
[api: FastAPI (Python)] ── REST API, đăng nhập, phân quyền, nghiệp vụ
    │        │                         │
    │     Redis ── hàng đợi + khoá     GitHub App (đọc repo, tạo issue)
    │        │
    │   [worker: Python] ── lấy việc từ hàng đợi → clone repo → gọi Claude → ghi kết quả
    │        │
    └──── Google Sheets (dữ liệu) ◄──┘
```

| Thành phần | Công nghệ | Nguồn |
|---|---|---|
| Giao diện | Next.js (App Router) + TypeScript strict + Tailwind CSS + shadcn/ui | PRD; [Đề xuất] giữ vì cần giao diện đẹp |
| REST API | Python 3.12+, FastAPI, Pydantic v2 | [Chủ dự án] Python; [Đề xuất] FastAPI |
| Worker | Python, chạy thành tiến trình riêng | [Đề xuất] |
| Hàng đợi | Redis + một thư viện hàng đợi Python (RQ hoặc arq, để người làm chọn) | [Đề xuất] |
| Khoá | Redis | PRD |
| Dữ liệu | Google Sheets qua service account | [Chủ dự án] |
| AI | Claude Agent SDK (Python), chỉ cho công cụ đọc | [Đề xuất] |
| GitHub | GitHub App, gọi REST API | PRD |
| Triển khai | Docker Compose: `web`, `api`, `worker`, `redis` | PRD |

**Vì sao web và api tách riêng:** chủ dự án muốn backend Python và muốn giao diện đẹp. Next.js với shadcn/ui là lựa chọn tốt nhất cho phần giao diện, còn FastAPI giữ toàn bộ nghiệp vụ. **Next.js không chứa logic nghiệp vụ và không gọi Google, GitHub hay Anthropic.**

**Kiểu dữ liệu dùng chung:** Pydantic là nguồn gốc. Kiểu TypeScript cho frontend được sinh tự động từ OpenAPI của FastAPI (ví dụ bằng `openapi-typescript`) để hai bên không lệch nhau. Form ở frontend vẫn validate bằng Zod để báo lỗi ngay khi gõ, nhưng backend luôn validate lại. **[Đề xuất]**

### 6.1 Cấu trúc thư mục

[Chủ dự án] chia `frontend/` và `backend/`. Phần bên trong là [Đề xuất]:

```
/
├── README.md                   # tổng quan + cách chạy (bắt buộc)
├── docker-compose.yml
├── .env.example
├── DECISIONS.md                # các giả định ghi thêm trong lúc làm
├── docs/superpowers/specs/     # tài liệu thiết kế
├── frontend/                   # Next.js: app/, components/, lib/ (api client, i18n)
└── backend/                    # MỘT project Python (pyproject.toml), chạy thành 2 tiến trình: api và worker
    ├── app/
    │   ├── api/                #   FastAPI: routers/, auth/, permissions/, services/
    │   ├── worker/             #   jobs/, repo_checkout/, ai/
    │   ├── prompts/            #   prompt + JSON schema cho AI
    │   └── core/               #   dùng chung cho api và worker:
    │       ├── models/         #     Pydantic models, enum
    │       ├── repositories/   #     interface + bản Google Sheets
    │       ├── sheets/         #     client Sheets: retry, ánh xạ theo tên cột
    │       ├── locks/          #     khoá Redis
    │       └── github/         #     GitHub App client
    └── tests/
```

## 7. Chức năng chi tiết

### 7.1 Đăng nhập
- Đăng nhập Google (OAuth) do **FastAPI xử lý** (ví dụ bằng Authlib). Chỉ email có trong tab `Users` với `active = TRUE` mới vào được. **[Đề xuất]**
- Session lưu phía server (trong Redis), trình duyệt chỉ giữ cookie `httpOnly`, `Secure`, `SameSite=Lax`. Next.js proxy `/api/*` sang FastAPI nên cookie dùng chung một domain.
- Chạy local: redirect URI là `http://localhost:3000/...`; cookie không bật `Secure` khi ở `localhost` (bật lại khi chạy HTTPS). OAuth consent screen để chế độ **External / Testing**, Admin thêm email các thành viên vào danh sách test user (tối đa 100, đủ cho 10–20 người). Như vậy dùng được cả Gmail cá nhân lẫn email công ty. **[Đề xuất]**
- Admin đầu tiên khai báo qua biến môi trường `BOOTSTRAP_ADMIN_EMAIL`. Lần đầu khởi động, nếu tab `Users` trống thì tự thêm email này với vai trò Admin. **[Đề xuất]**

### 7.2 Quản lý user (Admin)
- Xem danh sách, thêm user (email, tên, vai trò), đổi vai trò, khoá/mở (`active`). Không xoá cứng.

### 7.3 Dự án và repo (Admin)
- Tạo, sửa, lưu trữ (`archived`) dự án.
- **Chọn repo:** dropdown lấy từ GitHub API, gồm các repo mà GitHub App được cài. Không nhập token hay URL bằng tay. **Mỗi dự án gắn đúng một repo** [Chủ dự án]. Nếu repo chứa cả frontend và backend thì `code_paths` của màn hình có thể trỏ vào cả hai thư mục.
- **Chọn branch:** dropdown lấy từ API.
- `staging_url`: trường tuỳ chọn, để sẵn cho giai đoạn 2.
- **Gắn Google Sheet:** Admin tạo file Sheet trống, share quyền Editor cho email service account (giao diện hiện sẵn email này kèm nút copy), rồi dán Spreadsheet ID hoặc cả link. App kiểm tra quyền ghi; tab nào còn thiếu thì tự tạo kèm dòng tiêu đề.

### 7.4 Thành viên dự án (Admin, QA Lead)
- Thêm hoặc bỏ thành viên (chọn từ danh sách user đang active).

### 7.5 Màn hình và chia việc (Admin, QA Lead)
- CRUD màn hình: tên, mô tả, route trong app, `code_paths` (danh sách đường dẫn file hoặc thư mục trong repo, để AI đọc đúng chỗ).
- Giao một màn hình cho một hoặc nhiều tester, có deadline. Mỗi cặp (màn hình, tester) là một dòng `Assignments`.
- Trạng thái việc: `TODO` → `WRITING` → `IN_REVIEW` → `APPROVED` → `TESTED`. **[Đề xuất]** Trạng thái này **tự suy ra** từ test case, không bắt ai bấm đổi tay:
  - `TODO`: tester chưa tạo case nào cho màn hình này.
  - `WRITING`: có ít nhất một case `DRAFT`.
  - `IN_REVIEW`: không còn `DRAFT`, có ít nhất một case `IN_REVIEW`.
  - `APPROVED`: mọi case (trừ `DEPRECATED`) đã `APPROVED`.
  - `TESTED`: đã `APPROVED` và mọi case đã có kết quả trong ít nhất một run.
  - Backend tính lại và cập nhật cột `status` mỗi khi test case hoặc run thay đổi, để người mở Sheet vẫn đọc được.
- Trang **"Việc của tôi"** cho tester: các màn hình được giao, deadline, trạng thái, số case theo từng trạng thái. Việc sắp tới hạn hoặc quá hạn được đánh dấu rõ.

### 7.6 Test case

| Trường | Kiểu | Bắt buộc | Ghi chú |
|---|---|:-:|---|
| `id` | string | ✅ | Backend sinh, dạng `TC-000123`, đánh số **theo từng dự án**. Không cho sửa |
| `screen_id` | string | ✅ | |
| `title` | string | ✅ | |
| `precondition` | text | | |
| `test_data` | text | | |
| `steps` | list | ✅ | Mỗi bước gồm `action` và `expected`. Ít nhất 1 bước. Lưu trong Sheet dạng JSON string |
| `expected_result` | text | ✅ | |
| `severity` | enum | ✅ | `LOW` / `MEDIUM` / `HIGH` |
| `priority` | enum | ✅ | `P1` / `P2` / `P3` |
| `status` | enum | ✅ | `DRAFT` / `IN_REVIEW` / `APPROVED` / `DEPRECATED` |
| `created_by`, `updated_by` | email | ✅ | |
| `created_at`, `updated_at` | ISO datetime (UTC) | ✅ | |
| `version` | int | ✅ | Bắt đầu từ 1, tăng mỗi lần ghi |

**Chuyển trạng thái** **[Đề xuất]**
- Tester (hoặc QA Lead): `DRAFT` → `IN_REVIEW` (gửi duyệt).
- QA Lead/Admin: `IN_REVIEW` → `APPROVED` (duyệt), hoặc `IN_REVIEW` → `DRAFT` (trả lại, **bắt buộc kèm nhận xét**; nhận xét ghi vào `AuditLog` và hiện trên case).
- Sửa nội dung một case đang `APPROVED` hoặc `IN_REVIEW` thì case quay về `DRAFT`.
- Xoá = chuyển sang `DEPRECATED`. Không xoá cứng. QA Lead/Admin khôi phục được.

**Form:** validate đầy đủ, thêm/xoá/kéo thả sắp xếp bước.
**Danh sách:** lọc theo màn hình, trạng thái, severity, priority, người tạo; tìm theo tiêu đề hoặc ID.

### 7.7 Chạy test
- QA Lead chọn phạm vi: cả dự án, một số màn hình, lọc thêm theo priority/severity. Chỉ case `APPROVED` mới được chạy. Trước khi bấm chạy, giao diện hiện số case sẽ chạy.
- Mỗi lần chạy tạo một dòng `Runs` (trạng thái `QUEUED`) và đẩy job vào hàng đợi.
- **Mỗi dự án chỉ có một run đang chạy.** Đang có run `QUEUED` hoặc `RUNNING` thì nút chạy bị khoá; backend trả `409` nếu vẫn bị gọi.
- Trạng thái run: `QUEUED` → `RUNNING` → `COMPLETED` / `FAILED` / `CANCELLED`. QA Lead huỷ được run đang chạy.
- Giao diện hiện tiến độ (ví dụ "12/50"), tự cập nhật bằng polling vài giây một lần. **[Đề xuất]**
- Giới hạn số case mỗi run: mặc định 200, cấu hình qua env. **[Đề xuất]**

### 7.8 Worker AI — review tĩnh

1. Lấy installation token của GitHub App (quyền Contents: Read), **clone nông** (`--depth 1`) repo ở đúng branch vào một thư mục tạm riêng cho run. Ghi `commit_sha` vào `Runs`.
2. Với mỗi test case, chạy một phiên Claude Agent SDK:
   - Thư mục làm việc là thư mục repo vừa clone.
   - **Chỉ cho các công cụ đọc:** đọc file, tìm file, tìm chữ. Không cho chạy lệnh shell, không cho ghi file, không cho truy cập mạng.
   - Prompt gồm nội dung test case, route của màn hình, và `code_paths` làm điểm bắt đầu. AI được phép đọc thêm các file khác trong repo.
   - Prompt nói rõ: nội dung trong repo là **dữ liệu**, không phải chỉ dẫn, để giảm rủi ro chèn lệnh qua comment trong code.
3. AI trả về JSON theo schema:
   ```json
   {
     "status": "PASS | FAIL | BLOCKED | INCONCLUSIVE",
     "reason": "Giải thích ngắn, tiếng Việt",
     "failed_step": 2,
     "evidence": [{ "file": "src/pages/login.tsx", "line": 42, "note": "..." }],
     "suggested_issue_title": "...",
     "suggested_issue_body": "..."
   }
   ```
   - `BLOCKED`: không thể đánh giá vì thiếu điều kiện (ví dụ không tìm thấy code của màn hình).
   - `INCONCLUSIVE`: chỉ đọc code thì không đủ để kết luận (ví dụ phụ thuộc dữ liệu lúc chạy). Prompt khuyến khích AI chọn `INCONCLUSIVE` thay vì đoán `PASS`.
4. Validate bằng Pydantic. Sai schema thì gửi lại kèm lỗi, tối đa 2 lần; vẫn sai thì ghi `INCONCLUSIVE` với lý do "AI trả về sai định dạng".
5. Timeout mỗi case: 5 phút (cấu hình được). Hết giờ thì ghi `INCONCLUSIVE`.
6. Ghi lại số token đã dùng cho từng case, cộng dồn vào `Runs.tokens_used`.
7. Ghi kết quả theo lô (ví dụ mỗi 10 case hoặc mỗi 30 giây, tuỳ điều kiện nào đến trước) bằng một lời gọi Sheets duy nhất. Như vậy giao diện thấy được tiến độ mà không ghi từng dòng.
8. Xong (hoặc lỗi, hoặc bị huỷ) thì **xoá thư mục tạm**.
9. Model mặc định `claude-sonnet-5-5`, đổi được qua env `CLAUDE_MODEL`. **[Đề xuất]** Lý do: chạy nhiều case nên cân bằng giữa chất lượng và chi phí.
10. Prompt và schema để trong `backend/app/prompts/` cho dễ chỉnh.
11. Log của worker gắn `run_id`, chỉ ghi đường dẫn file và số dòng, **không bao giờ ghi nội dung source code**.

**Không dùng Docker sandbox ở giai đoạn 1** **[Đề xuất]**: AI chỉ đọc code, không chạy code của repo; repo là repo nội bộ; token chỉ có quyền đọc. Sandbox để dành cho khi AI cần build hoặc chạy app.

### 7.9 Duyệt kết quả và tạo GitHub Issue
- Màn hình kết quả của một run: thống kê PASS/FAIL/BLOCKED/INCONCLUSIVE, lọc theo status, mở từng case để xem lý do và bằng chứng. Bằng chứng hiện dạng `file:dòng` kèm link sang GitHub đúng commit.
- QA Lead chọn một case FAIL → xem trước issue (soạn sẵn từ `suggested_issue_title/body` cùng dữ liệu của case) → sửa nếu cần → bấm **"Tạo issue"**.
- QA Lead có thể đánh dấu một kết quả là **"AI sai"** (bỏ qua, không tạo issue). Thông tin này ghi vào `reviewed_by` và `review_note`. **[Đề xuất]**
- **Chống trùng:**
  - Mỗi issue có label `tc:TC-000123` và tiêu đề bắt đầu bằng `[TC-000123]`.
  - Trước khi tạo, tìm issue **đang mở** có label đó. Có thì **comment** kết quả mới vào issue cũ.
  - Label chưa tồn tại thì tự tạo.
- Nội dung issue: các bước, kết quả mong đợi, kết quả thực tế (lý do của AI), bằng chứng, severity, priority, branch, commit SHA, link về kết quả trong app.
- Lưu `issue_url` vào dòng `Results` tương ứng.

### 7.10 Dashboard (cơ bản)
- Tiến độ viết case theo tester và theo màn hình (số case theo trạng thái).
- Tỉ lệ PASS/FAIL của từng run gần đây; số issue đang mở do app tạo.

## 8. Mô hình dữ liệu trên Google Sheets

Hàng 1 của mỗi tab là tiêu đề cột. Code ánh xạ theo **tên cột**, không theo vị trí.

### 8.1 Spreadsheet hệ thống (1 file, ID trong `SYSTEM_SPREADSHEET_ID`)
| Tab | Cột |
|---|---|
| `Users` | `email`, `name`, `role`, `active`, `created_at` |
| `Projects` | `id`, `name`, `repo_full_name`, `branch`, `staging_url`, `spreadsheet_id`, `archived`, `created_at` |
| `ProjectMembers` | `project_id`, `email`, `added_at` |
| `AuditLog` | `at`, `actor`, `action`, `entity`, `entity_id`, `diff_json` (dùng cho thay đổi cấp hệ thống) **[Đề xuất]** |

### 8.2 Spreadsheet theo dự án (1 file mỗi dự án)
| Tab | Cột |
|---|---|
| `Meta` | `key`, `value` (lưu bộ đếm ID, ví dụ `next_tc_id`) **[Đề xuất]** |
| `Screens` | `id`, `name`, `description`, `route`, `code_paths`, `created_at` |
| `Assignments` | `id`, `screen_id`, `assignee_email`, `deadline`, `status`, `updated_at` |
| `TestCases` | các trường ở mục 7.6 |
| `Runs` | `id`, `triggered_by`, `scope`, `branch`, `commit_sha`, `status`, `started_at`, `finished_at`, `total`, `passed`, `failed`, `tokens_used` |
| `Results` | `id`, `run_id`, `test_case_id`, `status`, `reason`, `failed_step`, `evidence_json`, `tokens_used`, `issue_url`, `reviewed_by`, `review_note`, `created_at` |
| `AuditLog` | `at`, `actor`, `action`, `entity`, `entity_id`, `diff_json` |

So với PRD, `Results` có thêm `id`, `tokens_used` và `review_note`; thêm tab `Meta`. **[Đề xuất]**

## 9. Quy tắc ghi dữ liệu đồng thời (bắt buộc)

1. **Chỉ backend (api, worker) được ghi Sheet**, qua service account. Mọi người khác chỉ có quyền **xem** file Sheet. Admin tự share quyền xem trên Google Drive.
2. **Thêm mới** dùng `spreadsheets.values.append`.
3. **Sinh ID:** lấy khoá Redis `lock:id:<project_id>:<entity>` → đọc bộ đếm trong `Meta` → tăng → ghi lại → nhả khoá.
4. **Sửa bản ghi:**
   - Lấy khoá Redis `lock:<entity>:<id>` (TTL 10 giây).
   - **Đọc lại** để tìm dòng theo cột `id`. Không dùng số dòng đã lưu từ trước.
   - So `version` với version client gửi lên. Lệch thì trả **HTTP 409** kèm bản mới nhất và người sửa cuối. Giao diện báo: *"Case này vừa được [tên người sửa] cập nhật. Vui lòng tải lại."* **[Chủ dự án]** Chỉ cần vậy, không so sánh hay gộp.
   - Khớp thì ghi dòng, tăng `version`, ghi `AuditLog`, rồi nhả khoá.
   - Không lấy được khoá trong vài giây thì trả `409` hoặc `503` kèm thông báo thử lại.
5. **Worker ghi theo lô** bằng `batchUpdate` hoặc `append` nhiều dòng một lần, và chỉ ghi vào `Runs` và `Results`, nên không đụng tới dữ liệu tester đang sửa.
6. Lỗi `429` hoặc `5xx` từ Google: retry theo exponential backoff kèm jitter, tối đa khoảng 5 lần.
7. **Cache có chọn lọc** **[Đề xuất]**: mọi request đi qua một service account, mà Google giới hạn khoảng 60 lượt đọc/phút cho mỗi user. Vì vậy:
   - Thông tin user, vai trò và danh sách thành viên dự án (đọc ở mọi request để kiểm tra quyền) được cache trong Redis vài phút, và xoá cache ngay khi các tab này bị ghi.
   - Khi tìm dòng theo `id`, chỉ đọc cột `id` (một lượt đọc nhỏ) rồi đọc đúng dòng cần, không đọc cả tab.
   - Dữ liệu nghiệp vụ (test case, kết quả) không cache. Lớp repository được thiết kế để cắm thêm cache sau mà không phải sửa nghiệp vụ.
8. **Mọi thao tác với Sheet đi qua lớp repository** trong `backend/app/core/repositories` (ví dụ `TestCaseRepository`), có interface rõ ràng để sau này đổi sang PostgreSQL mà không phải sửa nghiệp vụ. Router và service không được gọi Google Sheets API trực tiếp.
9. **Bắt buộc có test:** hai người cùng sửa một case với cùng `version` thì một người nhận 409. Thêm test hai request tạo case song song không bị trùng ID.

## 10. Tích hợp

### 10.1 Google
- **OAuth** (đăng nhập): OAuth Client trong Google Cloud.
- **Sheets**: Service Account; file Sheet được share quyền Editor cho email service account. Thư viện: `google-api-python-client` hoặc `gspread` (người làm chọn).

### 10.2 GitHub
- **GitHub App**, chỉ cài vào các repo cần test. Quyền: `Contents: Read-only`, `Issues: Read & write`, `Metadata: Read-only`.
- Dùng installation token ngắn hạn.
- **Hỗ trợ nhiều installation** (nhiều organization): app tự liệt kê các installation của GitHub App rồi gộp danh sách repo, nên không cần biến `GITHUB_APP_INSTALLATION_ID`. **[Đề xuất]** Lý do: PRD để ngỏ chuyện nhiều organization, mà làm vậy cũng không tốn thêm bao nhiêu.

### 10.3 Anthropic
- Claude Agent SDK (Python), key `ANTHROPIC_API_KEY` chỉ nằm ở worker.

## 11. Giao diện

**[Chủ dự án]:** đẹp, dễ nhìn, dễ dùng. Các nguyên tắc **[Đề xuất]**:
- shadcn/ui + Tailwind; một bảng màu trung tính, một màu nhấn; hỗ trợ sáng/tối.
- Bố cục: thanh bên trái chứa danh sách dự án và các mục (Tổng quan, Màn hình, Test case, Chạy test, Kết quả, Thành viên, Cài đặt); thanh trên có tên dự án và tài khoản.
- Màu trạng thái nhất quán toàn app: PASS xanh lá, FAIL đỏ, BLOCKED cam, INCONCLUSIVE xám; tương tự cho trạng thái case.
- Bảng có lọc, tìm kiếm, phân trang; màn hình trống có hướng dẫn bước tiếp theo; thông báo dạng toast; xác nhận trước thao tác không hoàn tác được (tạo issue, huỷ run).
- Form test case: các bước là danh sách kéo thả, thêm bước bằng phím tắt; lưu nháp, gửi duyệt rõ ràng.
- Giao diện tiếng Việt, mọi chuỗi đi qua lớp i18n (ví dụ `next-intl`) để thêm ngôn ngữ sau.
- Tối ưu cho desktop, dùng được trên tablet.

Trước khi code giao diện, người làm nên dựng mockup các màn hình chính cho chủ dự án duyệt.

## 12. Bảo mật
- Không commit secret; chỉ commit `.env.example`.
- Token GitHub, key Google, key Anthropic chỉ ở api/worker, không bao giờ xuống trình duyệt. Next.js không giữ secret nào ngoài URL nội bộ của api.
- Worker: thư mục clone riêng cho từng run, xoá sau khi chạy; AI chỉ có công cụ đọc.
- Source code của repo được test không ghi vào log hay Sheet (chỉ đường dẫn file và số dòng). **[Đề xuất]** Cụ thể:
  - `reason` và `evidence[].note` chỉ mô tả bằng lời, không chép code. Prompt yêu cầu điều này, và backend loại bỏ mọi khối code trước khi lưu.
  - `suggested_issue_body` được phép trích đoạn ngắn (tối đa khoảng 10 dòng), vì issue nằm ngay trong repo đó. Đoạn trích này **không lưu vào Sheet**: worker giữ bản nháp issue trong Redis (hết hạn sau 30 ngày); hết hạn thì app soạn lại từ dữ liệu case cùng `reason`.
- Mọi thay đổi dữ liệu đều ghi `AuditLog`.

## 13. Yêu cầu phi chức năng
- Thao tác thông thường (mở danh sách, lưu case) dưới 2 giây trong điều kiện bình thường.
- Log của worker gắn `run_id`.
- Python có type hint đầy đủ, kiểm tra bằng `mypy --strict` (hoặc pyright strict); TypeScript ở chế độ `strict`.
- Test: `pytest` cho api, core và worker; với Google Sheets, test dùng bản giả (fake) của repository, cộng một vài test tích hợp chạy với Sheet thật khi có cấu hình.

## 14. Biến môi trường

```
# Đăng nhập
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
SESSION_SECRET=
BOOTSTRAP_ADMIN_EMAIL=
# Google Sheets
GOOGLE_SERVICE_ACCOUNT_JSON=        # nội dung JSON hoặc đường dẫn tới file key
SYSTEM_SPREADSHEET_ID=
# GitHub App
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
# AI
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-5-5
CASE_TIMEOUT_SECONDS=300
MAX_CASES_PER_RUN=200
# Hạ tầng
REDIS_URL=
APP_BASE_URL=
API_INTERNAL_URL=                   # để Next.js proxy sang FastAPI
```

## 15. Lộ trình

Mỗi mốc phải chạy được trọn vẹn trước khi sang mốc tiếp theo.

1. **M1 — Nền tảng:** monorepo, Docker Compose, đăng nhập Google, lớp Sheets (client + repository + khoá + retry), phân quyền, quản lý user, khung giao diện (layout, i18n, theme).
2. **M2 — Quản trị:** dự án, chọn repo/branch qua GitHub App, gắn Sheet, thành viên, màn hình, chia việc, "Việc của tôi".
3. **M3 — Test case:** form, danh sách, lọc, gửi duyệt, duyệt, optimistic locking (kèm test 409), audit log.
4. **M4 — Worker AI:** hàng đợi, clone repo, review tĩnh, ghi kết quả theo lô, tiến độ, huỷ run.
5. **M5 — Kết quả và issue:** màn hình kết quả, đánh dấu "AI sai", tạo issue hoặc comment, chống trùng.
6. **M6 — Dashboard.** Sau đó sang giai đoạn 2.

**Không làm bản chạy thử AI riêng** [Chủ dự án]. Làm xong thì chủ dự án đưa app cho team thử. Vì vậy prompt phải dễ chỉnh (để trong `backend/app/prompts/`), và màn hình kết quả có nút "AI sai" để thu phản hồi.

### 15.1 Chạy local và Docker [Chủ dự án]
- `docker compose up` dựng đủ `frontend` (cổng 3000), `api` (8000), `worker`, `redis`. Redis bật lưu xuống đĩa (AOF) để không mất session và hàng đợi khi khởi động lại. **[Đề xuất]**
- Có thêm cách chạy từng phần ngoài Docker cho lúc phát triển (Redis chạy trong Docker, frontend `npm run dev`, backend `uvicorn` và worker chạy trực tiếp).
- **`README.md`** ở thư mục gốc gồm: tổng quan dự án, kiến trúc tóm tắt, các bước chuẩn bị (tạo OAuth Client, Service Account và chia sẻ Sheet, tạo và cài GitHub App, lấy key Anthropic), điền `.env`, lệnh chạy bằng Docker và chạy từng phần, cách chạy test. Viết bằng tiếng Việt, đủ chi tiết để một người mới tự dựng được.

## 16. Giai đoạn 2 (định hướng, chưa làm)
- Khi có staging: AI thực hiện các bước bằng Playwright trên `staging_url`, chụp màn hình case FAIL. Thiết kế worker sao cho "cách test" là một thành phần thay được (review tĩnh / E2E).
- Lịch chạy định kỳ; tự đóng issue khi case pass lại; dashboard nâng cao.

## 17. Để lại cho người làm quyết định
- Thư viện hàng đợi Python (RQ hay arq), thư viện Sheets, thư viện OAuth.
- Chi tiết prompt cho AI.
- Cách trình bày cụ thể từng màn hình, trong khuôn khổ mục 11, kèm mockup cho chủ dự án duyệt.
- Cấu trúc file bên trong từng app.
- Khi gặp chỗ chưa rõ: ghi giả định vào cuối `DECISIONS.md`, không tự mở rộng phạm vi.

## 18. Câu hỏi còn mở (không chặn việc bắt đầu)
- Ngân sách token AI mỗi tháng (ảnh hưởng tới model mặc định và giới hạn mỗi run).
- Có cần import test case cũ từ Excel không (nếu có thì thêm vào M3).
- Thông tin đăng nhập staging (cho giai đoạn 2).
- Server và domain khi đưa lên dùng thật (hiện chỉ chạy local).

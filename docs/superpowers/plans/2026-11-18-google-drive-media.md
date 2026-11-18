# Google Drive làm nơi lưu ảnh/video (song song Cloudinary) — Kế hoạch

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Admin chọn nơi lưu ảnh/video cho từng project (`cloudinary` hoặc `drive`); mỗi project có thư mục riêng, tự tạo, trên cả hai nơi.

**Architecture:** Thêm `Project.storage`. Cloudinary giữ luồng ký-rồi-tải-thẳng. Drive đi qua backend: `POST .../media/upload` (multipart) → `DriveClient` (OAuth refresh token, gọi API Drive bằng `httpx`) → trả `Media` (link `drive.google.com/file/d/<ID>/view`, `public_id` = ID). Nơi lưu của một file nhận ra từ link của nó, nên link Cloudinary cũ vẫn dùng được.

**Tech Stack:** FastAPI, httpx, pytest (`httpx.MockTransport` cho Drive), Next.js 16 (đọc `frontend/AGENTS.md` và `node_modules/next/dist/docs/` trước khi viết route/page), vitest.

**Spec:** [docs/superpowers/specs/2026-11-18-google-drive-media-design.md](../specs/2026-11-18-google-drive-media-design.md)

## Global Constraints

- Giải thích và comment bằng tiếng Việt đơn giản; code dễ đọc. Báo lỗi cho người dùng bằng tiếng Việt.
- TDD: viết test, chạy thấy đỏ, rồi mới viết code. Trước khi báo xong chạy cả `cd backend && uv run pytest` (cùng `uv run ruff check .`/`mypy` nếu repo đang dùng) và `cd frontend && npm test && npm run typecheck && npm run lint`.
- Giới hạn: ảnh ≤ 10MB (`jpg,jpeg,png,webp,gif`), video ≤ 100MB (`mp4,mov,webm`); mỗi bước ≤ 5 media (đã có ở `MediaList`).
- Tester chỉ tải lên `purpose="guide"`; thư mục `evidence` chỉ dành cho agent.
- Thư mục: Cloudinary `ai-test-runner/<mã project>/<guide|evidence>`; Drive `<gốc>/<mã project>/<guide|evidence>`, gốc = `GOOGLE_DRIVE_ROOT_FOLDER_ID` (rỗng thì tạo thư mục `ai-test-runner` ở My Drive).
- Drive phạm vi OAuth: `https://www.googleapis.com/auth/drive.file`. Không in/commit giá trị `.env`; không để secret/refresh token lọt vào response hay log.
- Project cũ mặc định `storage = "cloudinary"` (ô trống trong Sheet = cloudinary). Cột mới nối vào **cuối** `PROJECT_COLUMNS`.
- **Cây làm việc đang có thay đổi chưa commit của chủ dự án** ở `SETUP.md`, `frontend/app/(app)/admin/projects/page.tsx`, `frontend/components/media/media-picker(.test).tsx`, `frontend/components/test-cases/case-form(.test).tsx`, `frontend/components/projects/create-project-dialog.tsx`, `frontend/messages/vi.json`. Không được revert/ghi đè; đọc `git diff` file đó trước khi sửa, sửa chồng lên. Khi commit các file này, chỉ stage phần của mình (`git add -p`); nếu không tách được thì dừng và hỏi chủ dự án.
- Commit theo Conventional Commits (type tiếng Anh, nội dung tiếng Việt có dấu), viết message bằng heredoc Git Bash, kết thúc bằng dòng `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Không push, không tạo PR, không commit vào `main`.
- Cuối mỗi đợt: ghi tiến độ vào file plan này (tick checkbox) và `HANDOFF.md`, rồi dừng để chủ dự án `/compact`.

## Review Focus

- Upload Drive lỗi giữa chừng (mạng/5xx): trả 502 "Không tải được lên Google Drive", không trả `Media` dở dang, file tạm được xoá.
- File sai loại hoặc quá dung lượng: bị từ chối (415/413) **trước** khi gọi Drive.
- Access token hết hạn (Drive trả 401): làm mới một lần rồi thử lại, không lặp vô hạn.
- Tên file/thư mục có dấu nháy `'` hoặc ký tự lạ: truy vấn tìm thư mục phải thoát ký tự, không lỗi 400.
- Hai upload đầu tiên cùng lúc của một project: không tạo hai thư mục trùng tên (khoá theo đường dẫn trong tiến trình).
- Project đang `drive` nhưng `.env` không còn cấu hình Drive: upload trả 503 "Chưa cấu hình Google Drive"; Admin không chọn được `drive` khi Drive chưa cấu hình (422).
- Đổi project từ cloudinary sang drive: link Cloudinary cũ vẫn qua kiểm tra và vẫn xoá được bằng Cloudinary; link Drive không bị gửi tới Cloudinary `destroy`.
- Link Drive do người dùng tự dán (`/file/d/<ID>/view` nhưng `public_id` khác ID): bị từ chối.

---

## ĐỢT 1 — Backend: dữ liệu và kiểm tra link

### Task 1: Trường `storage` của project

**Files:**
- Modify: `backend/app/core/models/project.py`, `backend/app/core/sheets/schema.py`, `backend/app/core/repositories/projects.py`, `backend/app/core/services/projects.py`, `backend/app/api/routers/projects.py`
- Test: `backend/tests/test_project_repository.py`, `backend/tests/test_projects_api.py`

**Interfaces:**
- Produces: `Storage = Literal["cloudinary", "drive"]` trong `models/project.py`; `Project.storage: Storage = "cloudinary"`; `UpdateProjectRequest.storage: Storage | None`; `ProjectService.update_project(..., storage: Storage | None = None)`.

- [x] **Step 1: Test đỏ** — `test_storage_defaults_to_cloudinary_and_round_trips` (repo: tạo project → `storage == "cloudinary"`; update `storage="drive"` → đọc lại được, ô Sheet ghi `drive`; ô trống đọc ra `cloudinary`). `test_only_admin_can_set_storage` (Admin PATCH `{"storage":"drive"}` → 200 khi Drive được bật; QA Lead PATCH → 403 vì **không** nằm trong `_SETTINGS_FIELDS`). `test_cannot_choose_drive_when_not_configured` (`services.drive is None` → 422 "Chưa cấu hình Google Drive"). Chạy `uv run pytest backend/tests/test_project_repository.py backend/tests/test_projects_api.py -k storage`, kỳ vọng FAIL.
- [x] **Step 2:** Thêm `"storage"` vào cuối `PROJECT_COLUMNS`; ánh xạ trong `_to_record/_from_record` (trống → `"cloudinary"`); thêm tham số `storage` vào `ProjectService.update_project` (vào dict `changes`); router `update_project` truyền `body.storage` và, nếu `body.storage == "drive"` mà `services.drive is None`, trả 422 với `NOT_CONFIGURED_DRIVE` (hằng số ở Task 2). Nếu `services.drive` chưa tồn tại ở Task này, thêm field `drive: DriveClient | None = None` vào `Services` ngay đây (kiểu tạm `Any | None`, Task 3 đổi kiểu thật).
- [x] **Step 3:** Chạy lại test Step 1 → PASS; chạy cả `backend/tests/` không hỏng test cũ.
- [x] **Step 4: Commit** `feat(backend): project có trường nơi lưu ảnh/video`.

### Task 2: Mô hình `Media` nhận cả Drive; kiểm tra link; link hiển thị

**Files:**
- Modify: `backend/app/core/models/media.py`, `backend/app/core/services/test_cases.py` (`_require_own_media`, nhận thêm `drive_enabled: bool = False`), `backend/app/api/routers/test_cases.py` (`service_for` truyền `drive_enabled=services.drive is not None`), `backend/app/api/routers/agent.py:186`, `backend/app/core/github/issue_format.py`
- Test: `backend/tests/test_media.py`, `backend/tests/test_issue_format.py`, `backend/tests/test_media_frames.py`

**Interfaces:**
- Produces (trong `models/media.py`):
  - `DRIVE_PREFIX = "https://drive.google.com/file/d/"`, `NOT_CONFIGURED_DRIVE = "Chưa cấu hình Google Drive"`
  - `def provider_of(media: Media) -> Literal["cloudinary", "drive"]` (theo prefix link)
  - `def ensure_own_media(items: Iterable[Media], cloud_name: str, drive_enabled: bool) -> None` — thay `ensure_own_cloud`; Cloudinary: như cũ (đúng `cloud_name`); Drive: cần `drive_enabled`, link phải khớp `^https://drive.google.com/file/d/<id>/view$` và `<id> == public_id`; ngược lại ném `ForeignMediaError`.
  - `def display_url(media: Media) -> str` — Cloudinary: `media.url`; Drive ảnh: `https://drive.google.com/thumbnail?id=<ID>&sz=w1600`; Drive video: `media.url` (link xem).
- `Media._only_cloudinary_https` đổi thành `_only_known_hosts`: chấp nhận cả hai prefix.

- [x] **Step 1: Test đỏ** (trong `test_media.py`): `test_media_accepts_cloudinary_and_drive_links`; `test_drive_link_with_mismatched_id_is_rejected` (đúng Review Focus cuối); `test_drive_requires_drive_enabled`; `test_provider_of`; `test_display_url_for_drive_image_is_thumbnail`. `test_issue_format.py`: ảnh Drive trong issue dùng `display_url` (thumbnail); video Drive chỉ có dòng `Video: <link>` và **không** có dòng `Ảnh cắt:`; video Cloudinary giữ nguyên. Kỳ vọng FAIL.
- [x] **Step 2:** Cài đặt như Interfaces; `_media_lines` bỏ dòng `Ảnh cắt` khi `video_frame_urls` rỗng; đổi mọi nơi gọi `ensure_own_cloud` sang `ensure_own_media`. Cập nhật test cũ dùng `ensure_own_cloud`.
- [x] **Step 3:** Chạy `uv run pytest backend/tests` → PASS.
- [x] **Step 4: Commit** `feat(backend): Media nhận link Google Drive và tạo link hiển thị`.

### Task 3: `DriveClient`

**Files:**
- Create: `backend/app/core/media/drive.py`
- Test: `backend/tests/test_drive.py`
- Modify: `backend/pyproject.toml` (chạy `uv add python-multipart` cho Task 5, nếu chưa có)

**Interfaces:**
- Consumes: `Media`, `MediaKind`, `MAX_BYTES`/`ALLOWED` từ `app/core/media/cloudinary.py` (chuyển hằng số dùng chung `MAX_BYTES` sang `app/core/media/limits.py` nếu cần tránh import vòng; Cloudinary import lại từ đó).
- Produces:
  - `class DriveClient(client_id: str, client_secret: str, refresh_token: str, root_folder_id: str = "", *, http: httpx.Client | None = None, now: Callable[[], float] = time.time)`
  - `def upload(self, project_id: str, purpose: Purpose, kind: MediaKind, filename: str, content_type: str, data: BinaryIO, size: int) -> Media`
  - `def destroy(self, public_id: str, kind: MediaKind) -> None` (thoả `MediaDestroyer`; 404 coi như đã xoá)
  - `class DriveError(Exception)` (thông điệp tiếng Việt, không chứa secret/token)

- [x] **Step 1: Test đỏ** với `httpx.MockTransport` ghi lại các request: `test_upload_creates_project_folders_then_uploads_and_shares` (gọi tạo `ai-test-runner` → `<mã project>` → `guide`, upload, rồi `POST /permissions` role `reader` type `anyone`; kết quả `Media.url == https://drive.google.com/file/d/<ID>/view`, `public_id == <ID>`); `test_folder_ids_are_cached` (upload lần 2 không tạo/tìm lại thư mục); `test_existing_folder_is_reused` (tìm thấy thư mục thì không tạo mới; truy vấn thoát dấu `'` trong tên); `test_refreshes_access_token_once_on_401`; `test_token_error_message_has_no_secret`; `test_concurrent_first_uploads_create_one_folder` (hai luồng); `test_destroy_deletes_by_id_and_ignores_404`; `test_upload_failure_raises_drive_error`.
- [x] **Step 2:** Cài đặt: lấy access token bằng `POST https://oauth2.googleapis.com/token` (`grant_type=refresh_token`), cache tới gần hết hạn; tìm-hoặc-tạo thư mục bằng `files.list` (`q` có `mimeType='application/vnd.google-apps.folder'`, `trashed=false`) và `files.create`, cache ID theo đường dẫn, khoá `threading.Lock` theo đường dẫn; ảnh dùng upload `multipart`, video dùng upload `resumable` (đọc `data` từng khúc, không nạp cả file vào RAM); sau upload tạo quyền `anyone/reader`. Tên file trên Drive: `<token ngẫu nhiên><đuôi gốc>` (không dùng tên gốc để tránh ký tự lạ).
- [x] **Step 3:** Chạy `uv run pytest backend/tests/test_drive.py` → PASS.
- [x] **Step 4: Commit** `feat(backend): client Google Drive để tải lên và xoá file`.

### Task 4: `MediaJanitor` chọn đúng nơi để xoá

**Files:**
- Modify: `backend/app/core/media/cloudinary.py` (`MediaJanitor.__init__(self, client: MediaDestroyer | None, *, drive: MediaDestroyer | None = None)`), `backend/app/core/services/test_cases.py` (không đổi logic, chỉ kiểm tra), `backend/app/core/services/evidence_retention.py` (kiểm tra)
- Test: `backend/tests/test_cloudinary.py` hoặc `test_media.py`, `backend/tests/test_evidence_retention.py`

**Interfaces:**
- Consumes: `provider_of` (Task 2), `DriveClient.destroy` (Task 3).

- [x] **Step 1: Test đỏ:** `test_janitor_routes_by_provider` (file Cloudinary → client Cloudinary, file Drive → client Drive, cái còn lại không bị gọi); `test_janitor_skips_drive_file_when_drive_not_configured` (không lỗi, chỉ ghi log); các test cũ của `MediaJanitor(client)` vẫn chạy.
- [x] **Step 2:** Cài đặt route theo `provider_of(item)` trong `_delete_all`.
- [x] **Step 3:** `uv run pytest backend/tests` → PASS.
- [x] **Step 4: Commit** `feat(backend): xoá file đúng nơi lưu (Cloudinary hoặc Drive)`.

### Task 5: Cấu hình, nối dây và hai endpoint upload

**Files:**
- Modify: `backend/app/settings.py` (`google_oauth_client_id`, `google_oauth_client_secret`, `google_oauth_refresh_token`, `google_drive_root_folder_id`, đều mặc định `""`), `backend/app/api/services.py` (`drive: DriveClient | None`, `build_services` dựng `DriveClient` khi đủ 3 biến OAuth, truyền vào `MediaJanitor(..., drive=...)`), `backend/app/api/routers/media.py`, `backend/app/api/routers/agent.py`, `.env.example`
- Test: `backend/tests/test_media_api.py`, `backend/tests/test_agent_results_api.py`, `backend/tests/conftest.py` (fixture `FakeDrive`)

**Interfaces:**
- Produces:
  - `POST /api/projects/{project_id}/media/upload` — multipart: `file`, `purpose="guide"`; quyền `Action.EDIT_TEST_CASE`; trả `Media`. Chỉ khi `project.storage == "drive"`, sai thì 409 "Dự án này lưu ảnh/video trên Cloudinary".
  - `POST /api/agent/projects/{project_id}/media/upload` — multipart: `file`; xác thực token agent; `purpose="evidence"`; trả `Media`.
  - `GET /api/agent/projects/{project_id}/media/storage` → `{"storage": "cloudinary"|"drive"}`.
  - `POST .../media/sign` (cả hai bản) trả 409 nếu `project.storage != "cloudinary"`.
  - Dùng chung hàm `kind_of_upload(content_type: str, size: int) -> MediaKind` ném `HTTPException` 415/413.

- [x] **Step 1: Test đỏ:** upload thành công trả `Media` và gọi `FakeDrive.upload` đúng `project_id/purpose`; `test_upload_rejects_wrong_type_before_calling_drive`; `test_upload_rejects_too_large_before_calling_drive`; `test_upload_503_when_drive_not_configured`; `test_upload_409_for_cloudinary_project`; `test_sign_409_for_drive_project`; `test_viewer_cannot_upload`; `test_tester_cannot_upload_evidence_purpose`; `test_agent_upload_requires_token`; `test_drive_error_returns_502` (không lộ chi tiết); `test_storage_endpoint`.
- [x] **Step 2:** Cài đặt; chép file upload vào `SpooledTemporaryFile` rồi truyền cho `DriveClient.upload` (xoá tạm sau khi xong, kể cả khi lỗi). `.env.example` thêm 4 biến mới (giá trị rỗng, có chú thích tiếng Việt).
- [x] **Step 3:** `uv run pytest backend/tests` và ruff/mypy → PASS.
- [x] **Step 4: Commit** `feat(backend): API tải ảnh/video lên Google Drive`.

### Task 6: Script lấy refresh token

**Files:**
- Create: `backend/app/tools/drive_auth.py`
- Test: `backend/tests/test_drive_auth.py`

**Interfaces:**
- Produces: `python -m app.tools.drive_auth` — đọc `GOOGLE_OAUTH_CLIENT_ID/SECRET` từ môi trường, mở trình duyệt tới màn hình đồng ý (`access_type=offline`, `prompt=consent`, scope `drive.file`), nhận mã ở `http://localhost:8765` (loopback), đổi lấy refresh token và **in đúng một dòng** `GOOGLE_OAUTH_REFRESH_TOKEN=...` (để chủ dự án tự dán vào `.env`; script không ghi file). Hàm thuần `build_auth_url(client_id, redirect_uri) -> str` và `exchange_code(code, ..., http) -> str` để test.

- [x] **Step 1: Test đỏ:** `build_auth_url` có đủ tham số (`scope`, `access_type=offline`, `prompt=consent`); `exchange_code` dùng `httpx.MockTransport`, trả refresh token; thiếu `refresh_token` trong phản hồi → lỗi tiếng Việt rõ ràng; không in client secret.
- [x] **Step 2:** Cài đặt. **Step 3:** test PASS. **Step 4: Commit** `feat(backend): script lấy refresh token Google Drive`.

> **Cuối Đợt 1:** chạy toàn bộ `uv run pytest`, tick checkbox, ghi HANDOFF, dừng chờ `/compact`.

---

## ĐỢT 2 — Frontend

### Task 7: Kiểu API và hàm link hiển thị

**Files:**
- Modify: `frontend/lib/api/openapi.json`, `frontend/lib/api/schema.d.ts` (sinh bằng `npm run gen:api` từ `frontend`), `frontend/lib/use-projects.ts` (`UpdateProjectInput` thêm `storage`)
- Create: `frontend/lib/media/display.ts`
- Test: `frontend/lib/media/display.test.ts`

**Interfaces:**
- Produces: `isDrive(media: Media): boolean`; `displayUrl(media: Media): string` (ảnh Drive → `https://drive.google.com/thumbnail?id=<ID>&sz=w1600`, còn lại → `media.url`); `embedUrl(media: Media): string | null` (video Drive → `https://drive.google.com/file/d/<ID>/preview`, còn lại `null`). Phải khớp với `display_url` ở backend (Task 2).

- [ ] **Step 1: Test đỏ** cho ba hàm (ảnh Drive, video Drive, ảnh/video Cloudinary). **Step 2:** cài đặt, `npm run gen:api`. **Step 3:** `npm test` PASS. **Step 4: Commit** `feat(frontend): hàm tạo link hiển thị ảnh/video theo nơi lưu`.

### Task 8: Upload theo nơi lưu và hiển thị

**Files:**
- Modify: `frontend/lib/media/upload.ts` (`Options` thêm `storage: "cloudinary" | "drive"`; nhánh `drive`: `XMLHttpRequest` POST `FormData{file, purpose:"guide"}` tới `/api/projects/{id}/media/upload`, cookie `same-origin` như `api`, giữ `onProgress`/`signal`, kiểm tra tại chỗ như cũ, mã lỗi 413/415/5xx → `UploadError("tooLarge"|"badType"|"uploadFailed")`), `frontend/components/media/media-picker.tsx`, `frontend/components/media/media-lightbox.tsx`, `frontend/components/results/result-detail.tsx` (dùng `displayUrl`; video Drive dùng `<iframe src={embedUrl(media)}>`), nơi gọi `MediaPicker` (truyền `storage` từ `useProject`)
- Test: `frontend/lib/media/upload.test.ts`, `frontend/components/media/media-picker.test.tsx`, `frontend/components/results/result-detail.test.tsx`

- [ ] **Step 1: Test đỏ:** `upload` với `storage:"drive"` gọi `/media/upload` (không gọi `/sign`) và trả `Media` từ phản hồi; mã 413 → `tooLarge`; picker hiện ảnh Drive bằng thumbnail và video Drive bằng iframe; ảnh/video Cloudinary hiển thị như cũ (test cũ không đổi).
- [ ] **Step 2:** Cài đặt. `media-picker.tsx(+.test)` đang có thay đổi chưa commit của chủ dự án: đọc `git diff` trước, sửa chồng lên. **Step 3:** `npm test && npm run typecheck && npm run lint` PASS. **Step 4: Commit** `feat(frontend): tải và xem ảnh/video theo nơi lưu của dự án`.

### Task 9: Admin chọn nơi lưu cho project

**Files:**
- Modify: `frontend/app/(app)/admin/projects/page.tsx` (thêm cột/ô chọn "Nơi lưu ảnh/video": Cloudinary | Google Drive, gọi `useUpdateProject`; 422 hiện thông báo của backend), `frontend/messages/vi.json`
- Test: `frontend/app/(app)/admin/projects/page.test.tsx` (tạo nếu chưa có)

- [ ] **Step 1: Test đỏ:** đổi sang Google Drive gửi `PATCH {storage:"drive"}`; nhận 422 "Chưa cấu hình Google Drive" thì hiện lỗi và ô chọn quay về giá trị cũ. **Step 2:** cài đặt (file này đang có thay đổi chưa commit của chủ dự án). **Step 3:** PASS. **Step 4: Commit** `feat(frontend): Admin chọn nơi lưu ảnh/video cho từng dự án`.

> **Cuối Đợt 2:** chạy đủ `npm test`, typecheck, lint; tick, ghi HANDOFF, dừng chờ `/compact`.

---

## ĐỢT 3 — Script Codex và tài liệu

### Task 10: `upload_evidence` biết hai nơi lưu

**Files:**
- Modify: `backend/app/tools/upload_evidence.py`
- Test: `backend/tests/test_upload_evidence.py`

- [ ] **Step 1: Test đỏ:** script gọi `GET .../media/storage` trước; `cloudinary` → luồng ký như cũ (test cũ giữ nguyên); `drive` → `POST .../media/upload` multipart với token, in `Media` JSON (`kind,url,public_id,note`); lỗi 503/502 → thông điệp tiếng Việt, token không bị in ra. **Step 2:** cài đặt, cập nhật docstring/`--help`. **Step 3:** PASS. **Step 4: Commit** `feat(backend): script bằng chứng của Codex hỗ trợ Google Drive`.

### Task 11: Tài liệu và thiết lập

**Files:**
- Modify: `SETUP.md` (đang có thay đổi chưa commit của chủ dự án — thêm mục mới ở cuối, không sửa phần đang có), `docs/codex-agent.md`, `HANDOFF.md`, `DECISIONS.md`, `docs/architecture.md` nếu có nhắc Cloudinary
- Test: không (tài liệu)

- [ ] **Step 1:** Viết mục "Bật Google Drive" trong `SETUP.md`: tạo project Google Cloud → bật Drive API → màn hình đồng ý OAuth (đặt app ở "In production" hoặc thêm email vào Test users; nếu để "Testing" thì refresh token hết hạn sau 7 ngày) → tạo OAuth client "Desktop/Web" (redirect `http://localhost:8765`) → điền `GOOGLE_OAUTH_CLIENT_ID/SECRET` vào `.env` → chạy `uv run python -m app.tools.drive_auth` → dán `GOOGLE_OAUTH_REFRESH_TOKEN` → (tuỳ chọn) `GOOGLE_DRIVE_ROOT_FOLDER_ID` → Admin chọn "Google Drive" ở trang dự án. Ghi giới hạn: 15GB chung Gmail/Photos, video Drive chỉ có ảnh đại diện trong issue GitHub.
- [ ] **Step 2:** `DECISIONS.md` thêm một quyết định (hai nơi lưu, chọn theo project, Drive đi qua backend, vì sao OAuth thay vì service account). Cập nhật `docs/codex-agent.md` (script tự nhận nơi lưu) và `HANDOFF.md` (tiến độ + việc còn lại: di chuyển file cũ giữa hai nơi, nếu cần).
- [ ] **Step 3: Commit** `docs: hướng dẫn bật Google Drive làm nơi lưu ảnh/video`.

> **Kết thúc:** chạy đủ hai bộ test, báo kết quả thật, hỏi chủ dự án về push/PR (chưa tự làm).

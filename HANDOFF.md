# HANDOFF — đọc file này đầu tiên

Cập nhật: 2026-11-15. Nhánh hiện tại: `feature/ai-agent-runner` (từ `develop`). **Không push, không tạo PR khi chưa được chủ dự án đồng ý.**

## Dự án đang ở đâu

AI Test Runner là web app nội bộ cho QA: Tester viết case, QA Lead duyệt, dữ liệu chính nằm trong Google Sheets. Case `APPROVED` được tạo thành GitHub issue trong **repo của dự án**. Codex chạy **ngoài** ứng dụng: đọc issue qua GitHub MCP, chạy Playwright, comment kết quả lên issue và gọi API token riêng để ghi tab `Runs`/`Results`.

M1–M3 đã nằm ở `develop`. Kế hoạch mới ở `docs/superpowers/plans/2026-11-14-case-to-issue-and-codex-agent.md`, thiết kế ở `docs/superpowers/specs/2026-11-14-case-to-issue-and-codex-agent-design.md`. Hướng worker Playwright cũ được giữ ở nhánh `feature/m4-playwright-worker` và tag `m4-playwright-v1`; **không** có worker hay tab Chạy test trên nhánh hiện tại. Chỉ mô hình và repository `Runs`/`Results` được lấy lại từ tag để phục vụ API agent.

Kế hoạch thông báo và bảng kết quả ở `docs/superpowers/plans/2026-11-14-notifications-results-dashboard.md` đã hoàn thành đủ 10 task. Ứng dụng hiện có chuông thông báo, trang Kết quả, hai tab "Đang làm"/"Đã xong", trang Tổng quan theo vai trò và hộp thoại dùng tốt hơn trên màn hình hẹp. Thông báo lưu trong Redis 30 ngày, tối đa 100 cái mỗi người; mất thông báo không làm mất dữ liệu chính. Cách cấu hình Codex và prompt mẫu ở `docs/codex-agent.md`. Tính năng **Chạy lại** đã xong: nút ở trang Kết quả (QA Lead/Admin) gọi `POST /api/projects/{project_id}/test-cases/{case_id}/request-rerun`, app comment + mở lại issue + gắn nhãn `needs-rerun`; khi có kết quả mới app tự bỏ nhãn này. Đã chạy thử trên repo thật `hieupt-ht/ShopHub` (RUN-0005). Codex **không** tự comment lên issue, app làm việc đó bằng GitHub App. Kiểm tra cuối: backend **388 test**, frontend **105 test** qua; `mypy app`, `ruff check`, typecheck, lint và build đều sạch.

## Đang làm (2026-11-16)

Bằng chứng ảnh/video (Cloudinary), test Android/iOS, giao bug cho dev. Thiết kế: `docs/superpowers/specs/2026-11-16-evidence-mobile-and-bug-assignment-design.md`. Kế hoạch 27 task, 8 đợt: `docs/superpowers/plans/2026-11-16-evidence-mobile-and-bug-assignment.md`. **Làm từng đợt một**: xong đợt thì đánh dấu `[x]` trong kế hoạch, ghi tiến độ ở đây, dừng cho chủ dự án `/compact`.

- Tiến độ: **đợt 1 xong** (Task 1–5, dữ liệu và mô hình; 2026-11-16): app tự thêm cột mới vào cuối tiêu đề Sheet lúc khởi động, có kiểu `Media`, cột mới của Projects/Screens/TestCases/Runs/Results. Backend 405 test, frontend 105 test qua. **Đợt 2 xong** (Task 6–9; 2026-11-17): công tắc "Cần QA duyệt" (tắt thì gửi là duyệt luôn, các case đang chờ được duyệt một lượt), sửa case đã duyệt tại chỗ kèm comment/`needs-rerun` lên issue, nút Duyệt/Trả lại mờ, lịch sử có phiên bản và giờ Việt Nam. Backend 431 test, frontend 112 test qua. Lưu ý: dự án cũ chưa có cột `require_review` đọc ra là TẮT duyệt. **Đợt 3 xong** (Task 10–13; 2026-11-17): backend ký upload Cloudinary (tester và agent), kiểm tra link ảnh đúng cloud, tự xoá file khi bỏ khỏi case; frontend có `MediaPicker` và form case 2 cột. Backend 453 test, frontend 134 test qua. Chưa kiểm tra bằng trình duyệt thật (1366×768, không cuộn cả trang). **Đợt 4 xong** (Task 14; 2026-11-17): issue có phiên bản case, nền tảng, loại test, regression, điểm bắt đầu, mã app Android/iOS, ảnh hướng dẫn và 6 ảnh cắt từ video; cập nhật issue giữ nhãn kết quả (`needs-rerun`, `test: fail`...) và nhãn tay. Backend 471 test qua. **Đợt 5 xong** (Task 15–20; 2026-11-17): Codex gửi được kết quả từng bước, video, ảnh, môi trường, phiên bản case (chuỗi evidence cũ vẫn nhận); chỉ giữ bằng chứng 5 lần chạy gần nhất mỗi case (file cũ bị xoá trên Cloudinary); comment issue có bảng từng bước; có script `python -m app.tools.upload_evidence`; API Kết quả trả đủ thông tin và lọc theo nền tảng/Run/regression; trang Kết quả có bộ lọc và bảng chi tiết bên phải. Backend 503 test, frontend 145 test qua. Chưa thử với Cloudinary/GitHub thật. **Đợt 6 xong** (Task 21–22; 2026-11-17): Màn hình có ô "Dev phụ trách" (tên GitHub, tự bỏ `@`, sai tên thì 422); khi Codex báo FAIL, issue được giao cho dev đó, có nhãn `bug: cần sửa` và dòng `Giao cho @dev` (gán lỗi thì comment cảnh báo, kết quả vẫn ghi; PASS gỡ nhãn bug, giữ người được giao). Backend 520 test, frontend 149 test qua. Chưa thử với GitHub thật. **Đợt 7 xong** (Task 23–25; 2026-11-17): QA Lead/Admin bấm "Chạy bộ regression" ở trang Kết quả, nhập bản build → app tạo run RUNNING gom các case regression đã duyệt, gắn `needs-rerun` kèm "Mã lần chạy" lên từng issue; Codex gửi kết quả kèm `run_id` (có thể gửi nhiều đợt, run tự COMPLETED khi đủ case, hoặc bấm "Kết thúc"); kết quả hiện ngay khi run còn chạy. Run regression không chặn và không bị chặn bởi run thường. Có thêm `GET regression-runs` (liệt kê run đang mở, ngoài plan, để hiện nút Kết thúc sau khi tải lại trang). `add_results` tự ghi kết quả (không nhận hàm `all_case_ids_done` như plan). Backend 543 test, frontend 156 test qua. Chưa thử với GitHub/Codex thật. **Đợt 8 – Task 26 xong** (2026-11-17): `docs/codex-agent.md` viết lại cho hai máy (Windows: web + Android; Mac: iOS), có cách cài, quay video, upload bằng chứng, hai prompt và quy tắc một phiên Codex mỗi máy; `.env.example` đã có sẵn ba biến `CLOUDINARY_*`. Còn **Task 27** (chạy thử thật trên `hieupt-ht/ShopHub`) cần chủ dự án điền `CLOUDINARY_*` vào `.env` và cùng làm.
- Lưu ý: `Sheet` thiếu cột giờ được **tự thêm** thay vì báo lỗi (hai test cũ đã đổi theo). `.venv` của backend đã được dựng lại bằng `uv sync` vì bản cũ trỏ tới miniconda không còn.

## Đang làm (2026-11-18): thêm Google Drive làm nơi lưu ảnh/video

Thiết kế `docs/superpowers/specs/2026-11-18-google-drive-media-design.md`, kế hoạch `docs/superpowers/plans/2026-11-18-google-drive-media.md` (11 task / 3 đợt). Admin chọn nơi lưu (Cloudinary hoặc Drive) cho **từng dự án**; mỗi dự án có thư mục riêng, tự tạo. Cloudinary vẫn giữ nguyên. **Làm từng đợt, xong thì dừng cho chủ dự án `/compact`.**

- **Đợt 1 xong** (Task 1–6, backend; 2026-11-18): `Project.storage` (cột `storage` cuối tab Projects, ô trống = cloudinary, chỉ Admin đổi qua PATCH, chọn drive khi chưa cấu hình thì 422); `Media` nhận cả link `drive.google.com/file/d/<ID>/view` (`ensure_own_media`, `provider_of`, `display_url`, `thumbnail_url`); `DriveClient` (OAuth refresh token, tự tạo thư mục `ai-test-runner/<mã dự án>/<guide|evidence>`, tải lên kiểu resumable, chia sẻ "ai có link", xoá theo ID); `MediaJanitor` xoá đúng nơi; endpoint `POST /api/projects/{id}/media/upload`, `POST /api/agent/projects/{id}/media/upload`, `GET .../media/storage`, `/sign` trả 409 nếu dự án lưu ở Drive; script `python -m app.tools.drive_auth` lấy refresh token; biến `.env` mới `GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN`, `GOOGLE_DRIVE_ROOT_FOLDER_ID`. Backend **656 test** qua, `mypy`, `ruff` sạch. Chưa thử với Google Drive thật.
- **Đợt 2 xong** (Task 7–9, frontend; 2026-11-18): `lib/media/display.ts` (`isDrive`, `displayUrl`, `embedUrl`), `uploadMedia` có tuỳ chọn `storage` (Drive: gửi multipart tới backend, 413/415 → báo đúng lỗi), `MediaPicker`/`MediaLightbox`/chi tiết kết quả hiện ảnh Drive bằng thumbnail và video Drive bằng iframe (`MediaVideo`), `CaseForm` lấy `storage` từ `useProject` truyền xuống ô chọn ảnh, trang Admin có cột "Nơi lưu ảnh/video" (ô chọn; backend từ chối thì hiện lỗi và quay về giá trị cũ). Frontend **190 test** qua, typecheck + lint sạch. Chưa thử trình duyệt thật. Các commit chỉ chứa phần của mình; phần sửa dở của chủ dự án trong `media-picker`, `case-form`, `admin/projects/page.tsx`, `vi.json`, `SETUP.md` vẫn chưa commit.
- **Đợt 3 xong** (Task 10–11; 2026-11-18): script `upload_evidence` tự hỏi `GET .../media/storage` rồi chọn luồng (Cloudinary ký chữ ký; Drive gửi multipart cho app), lỗi 503/502/413/415 báo tiếng Việt, không lộ token; có phụ lục "Bật Google Drive" ở cuối `SETUP.md`, quyết định 40 trong `DECISIONS.md`, `docs/codex-agent.md` cập nhật. Backend **660 test** qua.
- **Còn lại:** thử với Google Drive thật (cần chủ dự án lấy refresh token), review cả nhánh, quyết định merge/PR.
- Lưu ý: cây làm việc đang có thay đổi chưa commit của chủ dự án ở `SETUP.md`, trang admin/projects, `media-picker`, `case-form`, `create-project-dialog`, `vi.json` — sửa chồng lên, không ghi đè, chỉ stage phần của mình.

## Đang làm (2026-11-18): ảnh/video cho màn hình + trang chi tiết màn hình

Thiết kế `docs/superpowers/specs/2026-11-18-screen-media-and-detail-design.md`, kế hoạch `docs/superpowers/plans/2026-11-18-screen-media-and-detail.md` (5 task / 2 đợt, làm kiểu Native trong một phiên). Giữ nguyên luật: chỉ Admin/QA Lead tạo-sửa-xoá màn hình; tester chỉ viết case trên màn hình được giao nhưng xem được mọi màn hình.

- **Đợt 1 xong** (Task 1–2, backend): `Screen.media` (cột `media_json` cuối tab Screens, Sheet cũ đọc ra rỗng), API tạo/sửa nhận `media` (link sai kho → 422, tối đa 5), bỏ ảnh khỏi màn hình hoặc xoá màn hình thì `MediaJanitor` xoá file; PATCH không gửi `media` thì giữ nguyên. Backend **669 test** qua, mypy/ruff sạch.
- **Đợt 2 xong** (Task 3–5, frontend): `ScreenFormDialog` có `MediaPicker` (khoá Lưu khi đang tải, dialog rộng hơn + cuộn), `ScreenMediaStrip`, trang `screens/[screenId]` (thông tin, ảnh/video, bảng case của màn hình, nút Sửa/Tạo case theo quyền, không tìm thấy → báo + link về), tên màn hình ở danh sách thành link, `CaseForm` hiện ảnh của màn hình đã chọn và nhắc "nhờ QA Lead giao việc" khi trống. Frontend **203 test** qua, typecheck + lint sạch. Chưa thử trình duyệt thật (1366×768).
- **Còn lại:** review cả nhánh (reviewer mới). Sau đó brainstorm việc 3 (Manual/Automation).
- Lưu ý: không chạy `ruff format` cả thư mục (nó sửa nhầm 40+ file); chỉ `ruff check`.

## Đã xong (2026-11-17): đăng nhập bằng email + mật khẩu

Thay hẳn Google OAuth. Thiết kế `docs/superpowers/specs/2026-11-17-password-login-design.md`, kế hoạch `docs/superpowers/plans/2026-11-17-password-login.md` (12 task / 4 đợt, đã làm hết).

- Backend: mật khẩu băm argon2, cột `password_hash` ở tab Users (không bao giờ trả ra API), `POST /api/auth/login`, khoá 5 lần sai / 15 phút, `POST /api/auth/change-password`, `POST /api/users/{email}/reset-password` (xoá mọi phiên cũ). Admin đầu tiên lấy từ `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD`; Admin cũ chưa có hash sẽ được đặt hash ở lần khởi động đầu. Đã gỡ Google OAuth và authlib. Service Account và Sheet riêng tư giữ nguyên.
- Frontend: trang đăng nhập email + mật khẩu, form tạo user có ô mật khẩu, nút chìa khoá "Đặt lại mật khẩu" ở mỗi dòng, mục "Đổi mật khẩu" trong menu người dùng ở thanh trên.
- Tài liệu (`SETUP.md`, `README.md`, `docs/architecture.md`, `.env.example`) đã đổi sang mật khẩu.
- Kiểm tra cuối: backend 604 test qua, mypy và ruff sạch; frontend 175 test qua, typecheck và lint sạch.
- Chưa làm: thử bằng trình duyệt thật; review toàn nhánh; quyết định merge/PR (chờ chủ dự án).

## Việc còn dở

1. Luồng end-to-end (duyệt case → issue → Codex chạy → API → app comment, đổi nhãn) và luồng Chạy lại đã chạy được trên `hieupt-ht/ShopHub`. Còn cần đối chiếu thêm tab `Results` và thông báo hoàn tất, và thử trường hợp PASS.
2. ~~Ảnh bằng chứng~~ Đã xong bằng Cloudinary (script `app.tools.upload_evidence`); chỉ còn chờ chạy thử thật (Task 27).
3. Kiểm tra giao diện bằng mắt ở trình duyệt thật, đặc biệt hộp thoại, chuông thông báo, các tab "Việc của tôi", trang Kết quả và Tổng quan trên màn hình hẹp. Test tự động frontend đã qua nhưng chưa thay thế kiểm tra này.

## Công nghệ và lệnh kiểm tra

- Backend: Python 3.12, FastAPI, Redis, Google Sheets, GitHub App; thư mục `backend/`, quản lý bằng `uv`.
- Frontend: Next.js 16, TypeScript, Tailwind, next-intl; thư mục `frontend/`. Đọc `frontend/AGENTS.md` và tài liệu trong `frontend/node_modules/next/dist/docs/` trước khi viết route.
- Backend: `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check`.
- Frontend: `cd frontend && npx vitest run && npm run typecheck && npm run lint`.
- Khi sửa API: `cd frontend && npm run gen:api`.

## Quy ước không được quên

- Chủ dự án là sinh viên đang học: giải thích bằng **tiếng Việt đơn giản**, code dễ đọc, comment tiếng Việt.
- TDD: viết test, xem đỏ, rồi mới sửa code. Chạy cả hai bộ test trước khi báo xong.
- Không commit thẳng vào `main`. Commit theo Conventional Commits: type tiếng Anh, mô tả tiếng Việt có dấu. Trên Windows dùng heredoc Git Bash cho message. Không push, không tạo PR khi chưa được đồng ý.
- Không in hay commit giá trị trong `.env`, `worker-projects.json`. `AGENT_API_TOKEN` chỉ ở `.env`/môi trường, không đưa vào Sheet, log hay response.
- Chỉ backend ghi Sheet, qua repository; chỉ `gateway.py` gọi Google. Lỗi API có `{"detail": "<câu tiếng Việt>"}`. Chuỗi giao diện đặt ở `frontend/messages/vi.json`.
- Mã case `TC-000001` có thể trùng giữa các dự án: mọi khoá dùng chung và mọi tìm kiếm issue phải kèm dự án hoặc repo.
- Google Sheets có hạn mức đọc khoảng 60 lần/phút; tránh thêm lượt đọc dày. Issue của repo công khai không được chứa `test_data` hay email người tạo/sửa.

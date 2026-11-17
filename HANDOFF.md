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

## Đang làm (2026-11-17): đăng nhập bằng email + mật khẩu

Thay Google OAuth. Thiết kế `docs/superpowers/specs/2026-11-17-password-login-design.md`, kế hoạch 12 task / 4 đợt `docs/superpowers/plans/2026-11-17-password-login.md`. **Đợt 1 xong** (Task 1–4): argon2, cột `password_hash` ở tab Users, `POST /api/auth/login`, khoá 5 lần sai/15 phút, Admin đầu tiên từ `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD`. Backend 578 test qua. Google OAuth còn trong code (gỡ ở đợt 2, Task 7). Việc kế: đợt 2 (đổi/đặt lại mật khẩu, tạo user có mật khẩu, gỡ OAuth).

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

# HANDOFF — đọc file này đầu tiên

Cập nhật: 2026-11-15. Nhánh hiện tại: `feature/ai-agent-runner` (từ `develop`). **Không push, không tạo PR khi chưa được chủ dự án đồng ý.**

## Dự án đang ở đâu

AI Test Runner là web app nội bộ cho QA: Tester viết case, QA Lead duyệt, dữ liệu chính nằm trong Google Sheets. Case `APPROVED` được tạo thành GitHub issue trong **repo của dự án**. Codex chạy **ngoài** ứng dụng: đọc issue qua GitHub MCP, chạy Playwright, comment kết quả lên issue và gọi API token riêng để ghi tab `Runs`/`Results`.

M1–M3 đã nằm ở `develop`. Kế hoạch mới ở `docs/superpowers/plans/2026-11-14-case-to-issue-and-codex-agent.md`, thiết kế ở `docs/superpowers/specs/2026-11-14-case-to-issue-and-codex-agent-design.md`. Hướng worker Playwright cũ được giữ ở nhánh `feature/m4-playwright-worker` và tag `m4-playwright-v1`; **không** có worker hay tab Chạy test trên nhánh hiện tại. Chỉ mô hình và repository `Runs`/`Results` được lấy lại từ tag để phục vụ API agent.

Kế hoạch thông báo và bảng kết quả ở `docs/superpowers/plans/2026-11-14-notifications-results-dashboard.md` đã hoàn thành đủ 10 task. Ứng dụng hiện có chuông thông báo, trang Kết quả, hai tab "Đang làm"/"Đã xong", trang Tổng quan theo vai trò và hộp thoại dùng tốt hơn trên màn hình hẹp. Thông báo lưu trong Redis 30 ngày, tối đa 100 cái mỗi người; mất thông báo không làm mất dữ liệu chính. Cách cấu hình Codex và prompt mẫu ở `docs/codex-agent.md`. Tính năng **Chạy lại** đã xong: nút ở trang Kết quả (QA Lead/Admin) gọi `POST /api/projects/{project_id}/test-cases/{case_id}/request-rerun`, app comment + mở lại issue + gắn nhãn `needs-rerun`; khi có kết quả mới app tự bỏ nhãn này. Đã chạy thử trên repo thật `hieupt-ht/ShopHub` (RUN-0005). Codex **không** tự comment lên issue, app làm việc đó bằng GitHub App. Kiểm tra cuối: backend **388 test**, frontend **105 test** qua; `mypy app`, `ruff check`, typecheck, lint và build đều sạch.

## Việc còn dở

1. Luồng end-to-end (duyệt case → issue → Codex chạy → API → app comment, đổi nhãn) và luồng Chạy lại đã chạy được trên `hieupt-ht/ShopHub`. Còn cần đối chiếu thêm tab `Results` và thông báo hoàn tất, và thử trường hợp PASS.
2. Ảnh bằng chứng: app chỉ nhận link `https://`. Codex hiện lưu ảnh trên máy nên phải để trống `evidence`; cần cách đưa ảnh lên một địa chỉ https nếu muốn hiện trong app.
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

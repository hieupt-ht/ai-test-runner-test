# HANDOFF — đọc file này đầu tiên

Cập nhật: 2026-11-14. Nhánh hiện tại: `feature/ai-agent-runner` (từ `develop`). **Không push, không tạo PR khi chưa được chủ dự án đồng ý.**

## Dự án đang ở đâu

AI Test Runner là web app nội bộ cho QA: Tester viết case, QA Lead duyệt, dữ liệu chính nằm trong Google Sheets. Trên nhánh này, case `APPROVED` được tạo thành GitHub issue trong **repo của dự án**. Case đã có issue sẽ được cập nhật khi sửa, trả lại, ngừng dùng hoặc khôi phục. Codex chạy **ngoài** ứng dụng: đọc issue qua GitHub MCP, chạy Playwright, comment kết quả lên issue và gọi API token riêng để ghi tab `Runs`/`Results`.

M1–M3 đã nằm ở `develop`. Kế hoạch mới ở `docs/superpowers/plans/2026-11-14-case-to-issue-and-codex-agent.md`, thiết kế ở `docs/superpowers/specs/2026-11-14-case-to-issue-and-codex-agent-design.md`. Hướng worker Playwright cũ được giữ ở nhánh `feature/m4-playwright-worker` và tag `m4-playwright-v1`; **không** có worker hay tab Chạy test trên nhánh hiện tại. Chỉ mô hình và repository `Runs`/`Results` được lấy lại từ tag để phục vụ API agent.

Task 1–7 của kế hoạch đã được triển khai và commit theo từng task. Cách cấu hình và prompt mẫu ở `docs/codex-agent.md`. Kiểm tra cuối: backend **332 test**, frontend **59 test** qua; `mypy app`, `ruff check`, typecheck, lint và build đều sạch.

## Việc còn dở

1. **Chạy thử với repo thật** `hieupt-ht/126CQH01-NHOM-14`: đã xác nhận GitHub App đọc được repo và Issues; quyền ghi Issues chưa thử. Cần tạo/duyệt một case trong dự án thật rồi kiểm tra issue. Docker Desktop hiện chưa chạy trên máy này.
2. Mở Codex theo `docs/codex-agent.md`, dùng tài khoản test riêng của app, chạy kịch bản Playwright thật và đối chiếu comment trên issue với tab `Results`. `AGENT_API_TOKEN` hiện chưa được cấu hình; chưa có bằng chứng chạy end-to-end trên app thật.
3. Kiểm tra giao diện bằng mắt ở trình duyệt thật, đặc biệt nút đồng bộ lại trên màn hình hẹp. Test tự động frontend đã qua nhưng chưa thay thế kiểm tra này.
4. Sau khi xem kết quả thực tế, quyết định có cần thông báo khi issue đồng bộ lỗi hoặc khi agent ghi kết quả xong.

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

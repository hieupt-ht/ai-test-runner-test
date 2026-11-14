# HANDOFF — đọc file này đầu tiên

> **ĐANG Ở NHÁNH `feature/ai-agent-runner` (tách từ `develop`) — hướng MỚI, chưa code gì.** Nhánh này **chưa có M4** (không có worker Playwright, tab Chạy test, Runs/Results). Mọi thứ về hướng Playwright nằm ở nhánh `feature/m4-playwright-worker` / tag `m4-playwright-v1`; các mục "M4" bên dưới mô tả nhánh đó. Hướng mới: mỗi test case vào cả GitHub issue và Google Sheets, Codex agent đọc issue qua GitHub MCP rồi chạy test. **Việc đầu tiên:** đọc `docs/superpowers/specs/2026-11-14-case-to-issue-and-codex-agent-design.md`, hỏi chủ dự án 4 câu còn lại ở mục 6 (câu 5 đã chốt: issue nằm ở repo của app đang test) và xin duyệt thiết kế, rồi mới lập kế hoạch (skill `superpowers:writing-plans`) và code. Không push, không tạo PR khi chưa hỏi.

Cập nhật: 2026-11-14. Dành cho người (hoặc AI) tiếp tục dự án mà chưa từng thấy nó.

> **Mốc lưu hướng Playwright (2026-11-14):** toàn bộ M4 (worker Playwright chạy các bước tự động có cấu trúc, không dùng AI) nằm ở nhánh `feature/m4-playwright-worker`, đánh dấu bằng tag `m4-playwright-v1`. Chủ dự án đang cân nhắc một hướng khác (ví dụ AI có terminal hoặc MCP trình duyệt tự chạy hay tự viết bước, xem cuộc trao đổi về hướng A/B/C). Muốn quay lại hướng này: `git checkout m4-playwright-v1`. Nhánh `develop` và `main` chưa có M4.

## Dự án là gì

**AI Test Runner**: web app nội bộ cho đội QA. Tester viết test case, QA Lead duyệt, rồi một **worker chạy test tự động trên app thật bằng Playwright** và ghi kết quả (PASS/FAIL/BLOCKED/INCONCLUSIVE, bước lỗi, ảnh chụp) vào Google Sheets. Sau này AI chỉ điền sẵn các bước tự động; **hiện tại không dùng AI**.

- Backend: Python 3.12, FastAPI, Redis, Google Sheets làm nơi lưu dữ liệu (`backend/`, quản lý bằng `uv`).
- Frontend: Next.js 16 (bản mới, khác bản cũ: đọc `frontend/AGENTS.md` và `frontend/node_modules/next/dist/docs/` trước khi viết route), TypeScript, Tailwind, shadcn/base-ui, next-intl (mọi chữ giao diện nằm ở `frontend/messages/vi.json`).
- Tài liệu: thiết kế `docs/superpowers/specs/`, kế hoạch `docs/superpowers/plans/`, mọi quyết định đánh số ở `DECISIONS.md` (1–40). Cách cài đặt và chạy: `README.md`.

## Đang ở đâu

| Mốc | Trạng thái |
|---|---|
| M1 nền tảng, M2 quản trị dự án, M3 test case | Xong, đã merge vào `develop` (PR #1) |
| **M4 worker Playwright** | **Xong code và test, ở nhánh `feature/m4-playwright-worker`, chưa push, chưa PR** |
| M5 kết quả và tạo GitHub issue, M6 dashboard | Chưa làm |

Nhánh chồng lên nhau: `develop` ← `feature/m3-docs-and-notes` (DECISIONS 29–30, spec M4) ← `feature/m4-playwright-worker`. Chủ dự án quyết định merge/push/PR. **Không push, không tạo PR khi chưa hỏi.**

Kiểm tra gần nhất: backend `uv run pytest -q` = 404 qua; frontend `npx vitest run` = 98 qua; `mypy`, `ruff`, `tsc`, `eslint`, `npm run build` đều sạch.

## M4 hoạt động thế nào (để khỏi đọc lại cả plan)

1. Mỗi bước test case có trường tuỳ chọn `auto` (hành động chọn từ danh sách + cách tìm phần tử + giá trị), lưu **trong JSON của cột `steps`**, không thêm cột Sheet. Case cũ không có `auto`; API trả `auto: null` cho chúng.
2. QA Lead bấm Chạy ở tab "Chạy test" → API tạo run `QUEUED` ở tab `Runs` và đẩy job vào Redis (`queue:runs`). Mỗi dự án chỉ một run đang chạy (`QUEUED`/`RUNNING`), thêm thì 409.
3. Worker (`cd backend && uv run python -m app.worker`, **chạy thẳng trên máy, không Docker**) lấy job, đọc `worker-projects.json` (gitignore) để biết `app_path`, `start_command`, `app_url`, tài khoản test, `login_steps`; tự bật app, đăng nhập một lần, chạy từng case trong một ngữ cảnh trình duyệt mới, ghi kết quả theo lô (mỗi 10 case hoặc 30 giây), rồi tắt cả cây tiến trình của app.
4. Case thiếu bất kỳ bước tự động nào → `BLOCKED` (không chạy nửa chừng). Bước không đạt → `FAIL` kèm số bước và ảnh. Lỗi của worker hoặc hết giờ → `INCONCLUSIVE`. App không lên hoặc đăng nhập lỗi → cả run `FAILED` kèm lý do, không ghi FAIL cho từng case.
5. Huỷ run: đang chờ thì huỷ ngay; đang chạy thì đặt cờ, worker dừng sau case hiện tại. Worker khởi động lại sẽ đổi run `RUNNING` bị bỏ dở thành `FAILED`.

File chính: `backend/app/worker/` (`run_executor.py`, `case_runner.py`, `steps.py`, `app_process.py`, `config.py`), `backend/app/core/repositories/runs.py`, `backend/app/core/run_queue.py`, `backend/app/core/services/runs.py`, `backend/app/api/routers/runs.py`; frontend `components/runs/`, `components/test-cases/auto-step-fields.tsx`, `lib/use-runs.ts`.

## Việc còn dở (theo thứ tự)

1. **Form tạo/sửa test case đang bị "vỡ" ở vài chỗ** (chủ dự án báo nhưng chưa mô tả). Xin ảnh chụp, sửa trong commit riêng `fix(frontend): ...`. Phần "Tự động" mới thêm chưa được kiểm bằng mắt trên trình duyệt thật (nhất là màn hình hẹp ~375px).
2. **Chạy thử với app thật của chủ dự án**: cần đường dẫn repo, lệnh chạy, URL và một tài khoản test (app dùng đăng nhập email/mật khẩu, không dùng Google). Chưa ai làm; mới chỉ có test chạy thật trên một trang giả.
3. **Chưa kiểm bằng mắt** toàn bộ luồng web (tạo dự án chọn repo qua GitHub App, viết case, duyệt, tab Chạy test).
4. **Chủ dự án chưa chọn** cách khai báo cấu hình app cho worker: (A) giữ file `worker-projects.json` (hiện tại), (B) trang cấu hình chỉ Admin thấy, lưu vào file đó, (C) như B nhưng chỉ chọn lệnh trong danh sách. Lý do hiện làm A: `start_command` chạy thẳng trên máy chủ, không nên cho gõ qua web. Nếu làm B, giữ mật khẩu ngoài Sheet.
5. **Quyền tạo GitHub issue** (M5): theo spec, chỉ QA Lead/Admin xem FAIL rồi bấm "Tạo issue" (DECISIONS 30). Chủ dự án chưa quyết có cho tester không.
6. Lỗi nhỏ còn lại từ lượt rà cuối (không chặn merge): run đã chạy hết mà có cờ huỷ thì thành `CANCELLED`; `RunRepository.save` đọc Sheet 4 lần; lỗi thật tức thì có thể bị tính là hết giờ khi gần hết giờ của case; 20 dòng cuối output của app hiện cho mọi người xem dự án trong lý do run lỗi; run mất job khỏi Redis hiện "Đang chờ worker" mãi (chỉ gỡ bằng nút Huỷ); tiến độ hiện `0/N` tới lượt ghi đầu tiên; thiếu test trực tiếp cho nhánh hết giờ của `CaseSession`.
7. Chưa có thông báo cho các role (ví dụ báo QA Lead khi run xong): để sau M5.
8. Từ M3 còn lại: lỗi thô của Google/Redis có thể làm API 500 sau khi đã lưu (chủ dự án nói "từ từ"); tăng tốc ghi (ghi AuditLog và cập nhật trạng thái chạy nền).

## Chạy và kiểm tra nhanh

```bash
docker compose up -d redis
cd backend && uv sync && uv run playwright install chromium
uv run uvicorn app.main:create_app --factory --reload --port 8000     # api
uv run python -m app.worker                                           # worker (terminal khác)
cd ../frontend && npm install && npm run dev                          # web, cổng 3000

cd backend && uv run pytest -q && uv run mypy app && uv run ruff check
cd frontend && npx vitest run && npm run typecheck && npm run lint
```

`.env` ở thư mục gốc đã có Google OAuth, service account, SYSTEM_SPREADSHEET_ID, GitHub App (xem `.env.example`). **Không in giá trị trong `.env` ra, không commit nó.** `worker-projects.json` chứa mật khẩu tài khoản test, đã gitignore; mẫu ở `worker-projects.example.json`.

## Quy ước (chủ dự án đã yêu cầu rõ)

- Chủ dự án là **sinh viên đang học**: giải thích bằng **tiếng Việt đơn giản**, viết code dễ đọc, comment bằng tiếng Việt.
- **Gitflow**: nhánh `feature/<tên>` tách từ `develop`, PR vào `develop`, không commit thẳng vào `main`. **Conventional Commits**: type tiếng Anh, nội dung **tiếng Việt có dấu** (`feat(core): thêm khoá Redis`). Trên Windows viết message bằng heredoc trong Git Bash hoặc `git commit -F <file utf8>`, đừng dùng PowerShell 5.1 (hỏng dấu).
- **Không push, không tạo PR khi chưa được đồng ý.**
- Làm theo **TDD**: viết test, xem nó đỏ, rồi mới viết code. Mọi lỗi sửa đều kèm test đã đỏ trước.
- Tên mã (mã dự án `PRJ-0001`, mã run `RUN-0001`, mã case `TC-000001`): **mã run và mã case đánh số theo từng dự án nên lặp lại giữa các dự án**. Khoá Redis, đường dẫn thư mục ảnh và mọi khoá chung phải kèm mã dự án (đây là lỗi nghiêm trọng đã gặp ở M4, xem DECISIONS 32).
- Chỉ backend được ghi Google Sheets; mọi thao tác đi qua lớp repository; ghi theo khoá Redis (xem spec gốc mục 9).
- Lỗi API trả `{"detail": "<câu tiếng Việt>"}`; chuỗi giao diện nằm trong `frontend/messages/vi.json`.
- Hạn mức đọc Google Sheets khoảng 60 lượt/phút cho cả hệ thống: đừng thêm chỗ đọc Sheet dày (ví dụ làm mới giao diện nhanh hơn 5 giây).

## Cạm bẫy đã gặp

- Playwright `get_by_text` khớp **chuỗi con**, nên "Đăng nhập" khớp nhầm tiêu đề "Trang đăng nhập". Code đang dùng khớp trọn chữ cho "chữ hiển thị" (DECISIONS 35).
- Playwright sync API không cho hai phiên trong cùng một luồng (test chạy thật phải chạy executor trong luồng riêng).
- Tắt app phải tắt **cả cây tiến trình** (`npm run dev` sinh nhiều tiến trình con); dùng `psutil`.
- Terminal Windows dùng cp1252: script con in chữ có dấu có thể lỗi; test dùng chuỗi không dấu khi cần.
- Pydantic: `auto` có thể là `null` khi API trả về, schema của form phải dùng `.nullish()`.
- `learning-notes/` (ghi chú học HTML cho chủ dự án) **không commit**. Chưa viết ghi chú cho M4.

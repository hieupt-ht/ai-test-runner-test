# Thông báo, kết quả test và trang chủ — kế hoạch triển khai

> **Cho agent thực thi (Codex):** làm lần lượt từng task, TDD (viết test → chạy thấy đỏ → viết code → xanh → commit). Dùng checkbox `- [ ]` để theo dõi. Giải thích và comment bằng tiếng Việt đơn giản.

**Mục tiêu:** Người dùng có chuông thông báo, xem được kết quả test trong app, "Việc của tôi" có tab Đang làm/Đã xong, Tổng quan có nội dung theo vai trò, và hộp thoại tạo dự án hết vỡ.

**Kiến trúc:** Thông báo lưu trong Redis (đã có sẵn trong `Services.redis`), phát từ các service hiện có, đọc qua router mới `notifications`. Kết quả test đọc từ `RunRepository`/`ResultRepository` đã có. Phần còn lại là giao diện Next.js dùng React Query theo mẫu hiện có.

**Công nghệ:** FastAPI, Redis, Google Sheets, Next.js 16, TypeScript, next-intl, React Query, vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-notifications-results-dashboard-design.md` (đọc trước; đọc thêm `HANDOFF.md`, `AGENTS.md`, `frontend/AGENTS.md`).

## Ràng buộc chung
- Không push, không tạo PR; không commit vào `main`. Làm trên nhánh `feature/ai-agent-runner`.
- Commit theo Conventional Commits: type tiếng Anh, nội dung tiếng Việt có dấu; trên Windows viết message bằng heredoc Git Bash.
- Chỉ `gateway.py` gọi Google; chỉ backend ghi Sheet qua repository. Lỗi API dạng `{"detail": "<câu tiếng Việt>"}`. Chuỗi giao diện đặt ở `frontend/messages/vi.json`.
- Hạn mức đọc Sheets ~60 lần/phút: không thêm lượt đọc Sheet cho chuông (chuông chỉ dùng Redis).
- Gửi thông báo phải "cố gắng hết sức": bọc try/except, lỗi chỉ `logger.warning`, không được làm hỏng thao tác chính.
- Thông báo và issue không chứa `test_data`, mật khẩu, token, email người khác.
- Sửa API xong chạy `cd frontend && npm run gen:api`.
- Kiểm tra cuối mỗi task: `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check` và `cd frontend && npx vitest run && npm run typecheck && npm run lint`.

## Review Focus (đầu vào dễ gây lỗi, mỗi dòng có test ở task nêu trong ngoặc)
1. Người dùng không có thông báo nào → API trả danh sách rỗng và `unread = 0`, chuông không lỗi (Task 2).
2. Redis lỗi khi phát thông báo → thao tác chính (thêm thành viên, giao màn hình, trả/duyệt case) vẫn thành công (Task 3).
3. Người A cố đánh dấu đã đọc thông báo của người B → 404, không đổi gì (Task 2).
4. Tester xem kết quả → chỉ thấy case do mình tạo; không lộ case người khác (Task 4).
5. Thông báo sau 100 cái → cái cũ nhất bị cắt, không phình Redis (Task 1).

---

### Task 1: Kho thông báo trong Redis

**Files:**
- Create: `backend/app/core/notifications.py`
- Test: `backend/tests/core/test_notifications.py`

**Interfaces:**
- Produces:
  - `class Notification(BaseModel)`: `id: str`, `type: str`, `title: str`, `link: str`, `created_at: str` (ISO), `read: bool = False`.
  - `class NotificationStore`: `__init__(self, redis: Redis, *, max_items: int = 100, ttl_seconds: int = 30*24*3600)`.
    - `add(self, email: str, *, type: str, title: str, link: str) -> None`
    - `list(self, email: str) -> list[Notification]` (mới nhất trước)
    - `unread_count(self, email: str) -> int`
    - `mark_read(self, email: str, notification_id: str) -> bool` (False nếu không có)
    - `mark_all_read(self, email: str) -> None`
  - Email phải qua `normalize_email` (đã có ở `app.core`) trước khi dùng làm khoá.

- [ ] **Step 1:** Viết test (dùng fakeredis hoặc Redis giả như các test repository hiện có): `test_add_then_list_newest_first`, `test_unread_count_and_mark_read`, `test_mark_all_read`, `test_trims_to_max_items` (thêm 105 → còn 100, cái cũ nhất mất), `test_emails_are_isolated`, `test_mark_read_unknown_id_returns_false`.
- [ ] **Step 2:** Chạy `uv run pytest backend/tests/core/test_notifications.py -q`, thấy đỏ.
- [ ] **Step 3:** Cài `NotificationStore`; lưu mỗi người một danh sách Redis (JSON mỗi phần tử), đặt `expire` mỗi lần ghi, cắt bằng `ltrim`.
- [ ] **Step 4:** Chạy lại thấy xanh; chạy mypy/ruff.
- [ ] **Step 5:** Commit `feat(api): kho thông báo trong Redis`.

### Task 2: API thông báo

**Files:**
- Create: `backend/app/api/routers/notifications.py`
- Modify: `backend/app/api/services.py` (thêm `notifications: NotificationStore` vào `Services` và `build_services`), `backend/app/main.py` (thêm `app.include_router(notifications.router)`)
- Test: `backend/tests/api/test_notifications_api.py`

**Interfaces:**
- Consumes: `NotificationStore` (Task 1); dependency `CurrentUser` và `ServicesDep` như các router khác.
- Produces (tất cả chỉ thao tác trên thông báo của chính người đăng nhập):
  - `GET /api/notifications` → `{"items": list[Notification], "unread": int}`
  - `POST /api/notifications/{notification_id}/read` → 204; không có id → 404 `{"detail": "Không tìm thấy thông báo"}`
  - `POST /api/notifications/read-all` → 204

- [ ] **Step 1:** Viết test: `test_list_empty_returns_zero_unread`, `test_list_returns_only_my_notifications`, `test_mark_read_updates_unread`, `test_mark_other_users_notification_returns_404`, `test_requires_login` (401).
- [ ] **Step 2:** Chạy thấy đỏ.
- [ ] **Step 3:** Cài router theo mẫu `routers/me.py`; thêm trường `notifications` vào `Services` (kiểm tra chỗ test tạo `Services` giả và cập nhật cho khớp).
- [ ] **Step 4:** Chạy thấy xanh, chạy `npm run gen:api`.
- [ ] **Step 5:** Commit `feat(api): API đọc và đánh dấu đã đọc thông báo`.

### Task 3: Phát thông báo từ các sự kiện

**Files:**
- Create: `backend/app/core/services/notify.py`
- Modify: `backend/app/core/services/members.py`, `backend/app/api/routers/assignments.py` (hoặc service giao màn hình tương ứng), `backend/app/core/services/test_cases.py` (`_transition_case`: RETURN và APPROVE), `backend/app/api/routers/agent.py` (sau khi ghi kết quả)
- Test: `backend/tests/core/services/test_notify.py` và bổ sung test vào các test hiện có của từng service

**Interfaces:**
- Consumes: `NotificationStore.add`.
- Produces: `class Notifier`: `__init__(self, store: NotificationStore | None)`; mọi hàm đều bắt lỗi và không ném ra ngoài (`store is None` thì không làm gì):
  - `member_added(self, *, email: str, project_id: str, project_name: str) -> None`
  - `screen_assigned(self, *, email: str, project_id: str, screen_id: str, screen_name: str) -> None`
  - `case_returned(self, *, email: str, project_id: str, case_id: str, comment: str) -> None`
  - `case_approved(self, *, email: str, project_id: str, case_id: str) -> None`
  - `results_recorded(self, *, emails: list[str], project_id: str, run_id: str, failed: int, total: int) -> None`
  - `link` trỏ vào route app: `/projects/{id}`, `/projects/{id}/screens`, `/projects/{id}/test-cases/{case_id}`, `/projects/{id}/results`.

- [ ] **Step 1:** Viết test: mỗi hàm tạo đúng một thông báo cho đúng người với `link` đúng; `test_store_error_does_not_raise` (store ném lỗi → hàm không ném); `test_none_store_is_noop`. Thêm test ở service: thêm thành viên/giao màn hình/trả/duyệt case vẫn trả kết quả bình thường khi Redis lỗi.
- [ ] **Step 2:** Chạy thấy đỏ.
- [ ] **Step 3:** Cài `Notifier`; nối vào 5 chỗ trên. Người nhận: người được thêm/giao; người tạo case (`case.created_by`) cho trả/duyệt; QA Lead/Admin của dự án và người tạo từng case FAIL cho kết quả agent. Không gửi cho chính người thực hiện hành động.
- [ ] **Step 4:** Chạy cả bộ test backend xanh.
- [ ] **Step 5:** Commit `feat(api): phát thông báo khi thêm thành viên, giao việc, trả/duyệt case và có kết quả test`.

### Task 4: API đọc kết quả test

**Files:**
- Create: `backend/app/api/routers/results.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_results_api.py`

**Interfaces:**
- Consumes: `RunRepository.list_all`, `ResultRepository.list_for_run` (`backend/app/core/repositories/runs.py`), `scope_for` ở `api/project_scope.py`, quyền `Action.VIEW_PROJECT`.
- Produces: `GET /api/projects/{project_id}/results?status=` → `list[ResultItem]`, mỗi phần tử gồm `case_id`, `case_title`, `status`, `reason`, `failed_step: int | None`, `evidence: str`, `run_id`, `finished_at` (kết quả **mới nhất** của mỗi case). Tester chỉ thấy case có `created_by` là mình; QA Lead/Admin thấy hết. Dự án đã lưu trữ vẫn xem được.

- [ ] **Step 1:** Viết test: `test_qa_lead_sees_all_latest_results`, `test_tester_sees_only_own_cases`, `test_filter_by_status`, `test_non_member_forbidden`, `test_no_runs_returns_empty_list`.
- [ ] **Step 2:** Chạy thấy đỏ.
- [ ] **Step 3:** Cài router; đọc Runs/Results đúng một lần mỗi request, giữ kết quả mới nhất mỗi case bằng dict; dùng cache sẵn có nếu repository hỗ trợ. Không gọi GitHub.
- [ ] **Step 4:** Xanh; chạy `npm run gen:api`.
- [ ] **Step 5:** Commit `feat(api): API đọc kết quả test của dự án`.

### Task 5: Sửa hộp thoại tạo dự án

**Files:**
- Modify: `frontend/components/projects/create-project-dialog.tsx` (và component UI liên quan nếu lỗi nằm ở đó)
- Test: `frontend/components/projects/create-project-dialog.test.tsx` (tạo mới nếu chưa có)

- [ ] **Step 1:** Chạy `npm run dev`, mở `/admin/projects`, bấm tạo dự án, **xem bằng mắt** ở màn hình rộng và hẹp (≤ 400px); ghi lại hiện tượng vỡ (tràn, đè, không cuộn...).
- [ ] **Step 2:** Viết test mô tả hành vi mong muốn nếu kiểm tra được bằng test (ví dụ các trường và nút đều render, nút Tạo bấm được); chạy thấy đỏ nếu có thể. Nếu lỗi thuần bố cục thì ghi rõ trong commit là đã kiểm tra bằng mắt.
- [ ] **Step 3:** Sửa tận gốc (class Tailwind/bố cục; không dùng `!important`). Hộp thoại phải cuộn được khi nội dung dài và vừa màn hình hẹp.
- [ ] **Step 4:** Chạy vitest, typecheck, lint, build xanh.
- [ ] **Step 5:** Commit `fix: sửa giao diện hộp thoại tạo dự án`.

### Task 6: Chuông thông báo trên giao diện

**Files:**
- Create: `frontend/components/notifications/notification-bell.tsx`, `frontend/lib/use-notifications.ts`
- Modify: thanh đầu trang trong layout `frontend/app/(app)/` (tìm component header đang hiện tên người dùng), `frontend/messages/vi.json`
- Test: `frontend/lib/use-notifications.test.tsx`, `frontend/components/notifications/notification-bell.test.tsx`

**Interfaces:**
- Consumes: `GET /api/notifications`, `POST .../read`, `POST .../read-all` (Task 2, kiểu sinh ra trong `lib/api/schema.d.ts`); mẫu hook ở `lib/use-test-cases.ts` (`api`, `unwrap`).
- Produces: `useNotifications()` (React Query, `refetchInterval: 45_000`, tắt khi tab ẩn), `useMarkRead()`, `useMarkAllRead()`; `<NotificationBell />`.

- [ ] **Step 1:** Viết test: hiện huy hiệu số chưa đọc; ẩn huy hiệu khi 0; bấm một thông báo gọi `read` rồi điều hướng tới `link`; bấm "Đọc hết" gọi `read-all`; trạng thái rỗng hiện "Chưa có thông báo".
- [ ] **Step 2:** Chạy thấy đỏ.
- [ ] **Step 3:** Cài hook và component (dùng popover/dropdown có sẵn trong `components/ui`); chuỗi vào `vi.json`.
- [ ] **Step 4:** Xanh; xem bằng mắt ở màn hình hẹp.
- [ ] **Step 5:** Commit `feat: chuông thông báo trên thanh đầu trang`.

### Task 7: Tab Kết quả

**Files:**
- Create: `frontend/app/(app)/projects/[projectId]/results/page.tsx`, `frontend/lib/use-results.ts`
- Modify: thanh tab của trang dự án (tìm nơi khai báo các tab `projectTabs`), `frontend/messages/vi.json`
- Test: `frontend/lib/use-results.test.tsx`, `frontend/app/(app)/projects/[projectId]/results/page.test.tsx`

**Interfaces:**
- Consumes: `GET /api/projects/{id}/results` (Task 4).
- Produces: `useResults(projectId, status?)`; trang liệt kê case, huy hiệu trạng thái (PASS xanh, FAIL đỏ, BLOCKED/INCONCLUSIVE vàng), lý do, bước lỗi, link bằng chứng (chỉ mở `http(s)` — không render `javascript:`), bộ lọc trạng thái, trạng thái rỗng "Chưa có kết quả test".

- [ ] **Step 1:** Viết test: hiện đúng huy hiệu và lý do; lọc theo trạng thái gọi API với `status`; rỗng; link `javascript:...` không thành thẻ `<a>`.
- [ ] **Step 2:** Chạy thấy đỏ.
- [ ] **Step 3:** Cài trang và hook; thêm tab "Kết quả" vào thanh tab dự án.
- [ ] **Step 4:** Xanh; kiểm tra bằng mắt.
- [ ] **Step 5:** Commit `feat: tab Kết quả test trong dự án`.

### Task 8: Việc của tôi có tab Đang làm / Đã xong

**Files:**
- Modify: `frontend/app/(app)/my-work/page.tsx`, `frontend/messages/vi.json`
- Test: `frontend/app/(app)/my-work/page.test.tsx`

**Interfaces:**
- Consumes: `useMyAssignments()` (dữ liệu đã có, trường `status`).
- Produces: hai tab: **Đang làm** = `TODO | WRITING | IN_REVIEW`, **Đã xong** = `APPROVED | TESTED`; mỗi tab hiện số lượng; tab rỗng có câu giải thích riêng. Lọc ở frontend, không đổi backend.

- [ ] **Step 1:** Viết test: việc `APPROVED`/`TESTED` chỉ nằm ở "Đã xong"; việc còn lại ở "Đang làm"; số đếm đúng; việc xong không biến mất.
- [ ] **Step 2:** Chạy thấy đỏ.
- [ ] **Step 3:** Thêm tab (dùng `components/ui` có sẵn; mặc định tab Đang làm); giữ nguyên phần hiển thị case bị trả lại.
- [ ] **Step 4:** Xanh.
- [ ] **Step 5:** Commit `feat: tab Đang làm và Đã xong ở Việc của tôi`.

### Task 9: Tổng quan theo vai trò

**Files:**
- Modify: `frontend/app/(app)/page.tsx`, `frontend/messages/vi.json`
- Create: `frontend/components/overview/` (các thẻ nhỏ) nếu cần
- Test: `frontend/app/(app)/page.test.tsx`

**Interfaces:**
- Consumes: `useMe()`, `useMyAssignments()`, `useProjects()` (hooks có sẵn); `useResults` (Task 7) cho QA Lead/Admin của dự án đầu tiên. **Không** thêm API mới; không đọc Sheet thêm.
- Produces: Tester thấy việc đang làm, việc sắp hết hạn (≤ 3 ngày), số case bị trả lại. QA Lead thấy việc chờ duyệt và kết quả gần nhất. Admin thấy số dự án và kết quả gần nhất. Phần không có dữ liệu hiện trạng thái trống có chữ, không để trắng.

- [ ] **Step 1:** Viết test cho từng vai trò (mock `useMe`): đúng các thẻ hiện ra; không vai trò nào thấy thẻ của vai trò khác; trạng thái trống.
- [ ] **Step 2:** Chạy thấy đỏ.
- [ ] **Step 3:** Cài các thẻ bằng `Card` có sẵn.
- [ ] **Step 4:** Xanh; kiểm tra bằng mắt.
- [ ] **Step 5:** Commit `feat: trang Tổng quan theo vai trò`.

### Task 10: Cập nhật tài liệu

**Files:**
- Modify: `HANDOFF.md`, `DECISIONS.md`, `README.md` (nếu có mục liên quan)

- [ ] **Step 1:** `DECISIONS.md`: thêm quyết định — thông báo lưu Redis (30 ngày, 100 cái, mất cũng không hại dữ liệu chính); giữ nút Lưu trữ, không có xoá dự án; không xoá issue khi agent comment, issue chỉ đóng khi case ngừng dùng; chỉ Admin mở Google Sheet; việc xong không xoá, lọc bằng tab.
- [ ] **Step 2:** `HANDOFF.md`: cập nhật "Đang ở đâu" và "Việc còn dở".
- [ ] **Step 3:** Chạy cả hai bộ test một lần nữa, xanh. Commit `docs: ghi quyết định về thông báo, kết quả test và trang chủ`.

---

## Tự kiểm tra
- Bao phủ spec: chuông (Task 1–3, 6), tab Kết quả (4, 7), Việc của tôi (8), Tổng quan (9), hộp thoại vỡ (5), tài liệu/quyết định Lưu trữ-không xoá issue-quyền Sheet (10).
- Không có task xoá dự án hay gửi email, đúng với "không làm" của spec.

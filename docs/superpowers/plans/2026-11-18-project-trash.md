# Thùng rác dự án Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin chuyển dự án vào thùng rác, khôi phục, hoặc xoá vĩnh viễn (gõ tên để xác nhận) ngay ở trang Admin → Dự án.

**Architecture:** "Thùng rác" chính là cờ `archived` đã có; frontend chia danh sách thành 2 tab. Thêm `DELETE /api/projects/{id}` chỉ cho dự án đã lưu trữ: xoá các dòng thành viên rồi xoá dòng dự án trong Sheet hệ thống và ghi AuditLog. Không đụng Sheet riêng của dự án, issue GitHub, ảnh/video.

**Tech Stack:** FastAPI + pydantic + Google Sheets (`SheetTable`, fakeredis/`FakeSheetsGateway` trong test); Next.js 16, TanStack Query, next-intl, vitest.

**Spec:** `docs/superpowers/specs/2026-11-18-project-trash-design.md`

## Global Constraints

- Quyền xoá: `Action.MANAGE_PROJECTS` (chỉ Admin).
- Chỉ xoá được dự án `archived=True`; chưa lưu trữ → 409 "Hãy chuyển dự án vào thùng rác trước".
- Body xoá `{ "name": "<tên dự án>" }`; không khớp (so sau khi `strip()`) → 422; thành công → 204.
- Xoá thành viên TRƯỚC, xoá dòng dự án SAU; ghi AuditLog `DELETE` / `project` / mã dự án.
- Không xoá/đổi gì ở Sheet riêng của dự án, GitHub, Cloudinary/Drive.
- Chuỗi giao diện tiếng Việt đơn giản, thêm vào `frontend/messages/vi.json`; comment tiếng Việt.
- TDD. Chạy cả hai bộ test (backend `uv run pytest`, frontend `npx vitest run`) + `mypy app`, `ruff check app tests`, `tsc --noEmit`, `eslint` trước khi báo xong. KHÔNG chạy `ruff format` cả thư mục.
- Commit: Conventional Commits, type tiếng Anh, nội dung tiếng Việt có dấu, viết bằng heredoc, kết thúc `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Cây làm việc có sửa dở của chủ dự án (`frontend/app/(app)/admin/projects/page.tsx`, `frontend/messages/vi.json`, `create-project-dialog.tsx`, `media-picker*`, `case-form*`, `SETUP.md`, vài test backend). **Chỉ stage phần của mình**: với file đã sửa dở, tạo bản từ `git show HEAD:<file>` + chỉ phần của mình rồi stage riêng (như các đợt trước; cách làm: `git apply --cached` một patch chỉ chứa dòng của mình). Test backend mới đặt ở file MỚI để khỏi đụng file sửa dở.
- Không push, không tạo PR.

## Review Focus

1. Xoá dự án CHƯA lưu trữ → 409 và không mất gì (dự án + thành viên còn nguyên).
2. Gõ sai tên → 422 và không xoá gì; tên thừa khoảng trắng đầu/cuối vẫn khớp.
3. Người không phải Admin (kể cả QA Lead là thành viên) gọi DELETE → 403, không xoá.
4. Xoá dự án A không xoá thành viên của dự án B, kể cả cùng email.
5. Xoá xong, `GET /api/projects` không còn dự án; tạo lại dự án với cùng Sheet được (không còn bị coi là "Sheet đã dùng").

---

### Task 1: Repository xoá dự án và xoá thành viên theo dự án

**Files:**
- Modify: `backend/app/core/repositories/projects.py` (thêm `delete` cạnh `update`)
- Modify: `backend/app/core/repositories/members.py` (thêm `remove_all_for_project` cạnh `remove`)
- Test (file MỚI): `backend/tests/test_project_trash.py`

**Interfaces:**
- Consumes: `SheetTable.find_row_number(column, value)`, `SheetTable.read_rows_numbered()`, `SheetTable.delete_row(row_number)`, `self._cache.invalidate()`, `self._lock()` (đã có trong hai repo); `ProjectNotFoundError` (đã có).
- Produces: `ProjectRepository.delete(self, project_id: str) -> None` (raise `ProjectNotFoundError` nếu không có); `ProjectMemberRepository.remove_all_for_project(self, project_id: str) -> int` (trả số dòng đã xoá, 0 nếu không có).

- [x] **Step 1: Viết test đỏ** trong `backend/tests/test_project_trash.py`, dùng fixture `projects`, `members`, `gateway` và `make_project` của `tests/conftest.py`:
  - `test_delete_removes_project_row`: `make_project` rồi `projects.delete(p.id)` → `projects.get(p.id) is None` và `projects.list_all() == []`.
  - `test_delete_unknown_project_raises`: `projects.delete("PRJ-9999")` raise `ProjectNotFoundError`.
  - `test_delete_frees_spreadsheet_for_reuse`: sau khi xoá, `projects.find_by_spreadsheet(SHEET_A) is None`.
  - `test_remove_all_for_project_keeps_other_projects`: dự án A (sheet `SHEET_A`) và B (`SHEET_B`, tên khác) cùng thành viên `x@x.com` + A thêm `y@x.com` → `members.remove_all_for_project(A.id) == 2`, `members.list_for_project(A.id) == []`, `[m.email for m in members.list_for_project(B.id)] == ["x@x.com"]`.
  - `test_remove_all_for_project_with_no_members_returns_zero`.
- [x] **Step 2: Chạy** `cd backend && uv run pytest tests/test_project_trash.py -q`. Expected: FAIL (`AttributeError ... delete` / `remove_all_for_project`).
- [x] **Step 3: Cài `ProjectRepository.delete`**: trong `self._lock()`, `find_row_number("id", project_id)`, `None` → `ProjectNotFoundError(project_id)`, rồi `self._table.delete_row(row_number)`; ngoài khoá `self._cache.invalidate()` (giống `update`).
- [x] **Step 4: Cài `ProjectMemberRepository.remove_all_for_project`**: trong khoá lấy `read_rows_numbered()`, lọc dòng có `record["project_id"] == project_id`, xoá **từ số dòng lớn xuống nhỏ** (để số dòng chưa xoá không lệch), `invalidate()` cache, trả số dòng xoá.
- [x] **Step 5: Chạy lại** `uv run pytest tests/test_project_trash.py -q`. Expected: PASS.
- [x] **Step 6: Commit** (chỉ file của task): `git add backend/app/core/repositories/projects.py backend/app/core/repositories/members.py backend/tests/test_project_trash.py` rồi `feat(backend): repository xoá dự án và thành viên theo dự án`.

---

### Task 2: Service và API `DELETE /api/projects/{project_id}`

**Files:**
- Modify: `backend/app/core/services/projects.py` (thêm `delete_project`)
- Modify: `backend/app/api/routers/projects.py` (thêm route + model body)
- Test: `backend/tests/test_project_trash.py` (thêm test API)

**Interfaces:**
- Consumes: Task 1 (`ProjectRepository.delete`, `ProjectMemberRepository.remove_all_for_project`); `ProjectService._record(actor, action, project_id, diff)`; `load_project(services, user, project_id, action, allow_archived=True)`; `require`, `Action.MANAGE_PROJECTS`; `InvalidProjectInputError` (→ 422) trong router.
- Produces:
  - `class ProjectNotArchivedError(Exception)` trong `services/projects.py` (→ 409, `str(error)` = "Hãy chuyển dự án vào thùng rác trước").
  - `ProjectService.delete_project(self, actor: User, project: Project, *, confirm_name: str) -> None`.
  - `DELETE /api/projects/{project_id}` body `DeleteProjectRequest { name: str }` → 204.

- [x] **Step 1: Viết test API đỏ** (thêm vào `test_project_trash.py`; dùng `client_as_admin`, `client_for`, `make_project`; vì `TestClient.delete` không nhận body nên gọi `client.request("DELETE", url, json={"name": ...})`):
  - `test_admin_deletes_archived_project`: dự án `archived=True`, thành viên `lead@x.com` → 204; `GET /api/projects` trả `[]`; `members.list_for_project(id) == []`; `gateway.data[SYSTEM_SHEET_ID]["AuditLog"][-1][2:5] == ["DELETE", "project", id]`.
  - `test_delete_active_project_is_409` (Review Focus 1): dự án chưa lưu trữ → 409, dự án và thành viên vẫn còn.
  - `test_delete_with_wrong_name_is_422` (Review Focus 2): tên sai → 422, còn nguyên; `test_delete_name_is_trimmed`: `"  Dự án A  "` → 204.
  - `test_delete_requires_admin` (Review Focus 3): `client_for(app, users, "lead@x.com", Role.QA_LEAD)` là thành viên → 403 (hoặc mã mà `load_project` trả cho người không đủ quyền; dùng đúng mã thực tế rồi ghi vào test), dự án còn nguyên.
  - `test_delete_unknown_project_is_404`.
  - `test_delete_does_not_touch_other_project_members` (Review Focus 4) và `test_spreadsheet_can_be_reused_after_delete` (Review Focus 5: sau xoá, `POST /api/projects` với `create_body()` dùng `SHEET_A` → 201; `gateway.data[SHEET_A] = {}` trước như test tạo dự án hiện có).
- [x] **Step 2: Chạy** `uv run pytest tests/test_project_trash.py -q`. Expected: FAIL (405/404 vì chưa có route).
- [x] **Step 3: Cài `ProjectService.delete_project`**: nếu `not project.archived` → `ProjectNotArchivedError`; nếu `confirm_name.strip() != project.name` → `InvalidProjectInputError("Tên xác nhận không khớp")`; gọi `self._members.remove_all_for_project(project.id)` rồi `self._projects.delete(project.id)`; ghi `self._record(actor, "DELETE", project.id, {"name": ..., "repo_full_name": ..., "spreadsheet_id": ...})` (diff chỉ các trường này để còn dấu vết).
- [x] **Step 4: Thêm route** trong `routers/projects.py`: `@router.delete("/projects/{project_id}", status_code=204)`; `load_project(..., Action.MANAGE_PROJECTS, allow_archived=True)`; bắt `ProjectNotArchivedError` → 409, `InvalidProjectInputError` → 422, `LockTimeout` → 409 "Hệ thống đang bận, vui lòng thử lại" (giống route PATCH), `ProjectNotFoundError` → 404; trả `Response(status_code=204)`.
- [x] **Step 5: Chạy** `uv run pytest tests/test_project_trash.py -q` → PASS; sau đó `uv run pytest -q`, `uv run mypy app`, `uv run ruff check app tests` đều sạch.
- [x] **Step 6: Commit** `feat(backend): API xoá vĩnh viễn dự án đã lưu trữ` (chỉ file của task).

---

### Task 3: Giao diện thùng rác ở trang Admin

**Files:**
- Modify: `frontend/lib/api/openapi.json`, `frontend/lib/api/schema.d.ts` (sinh lại bằng `npm run gen:api` trong `frontend/`; backend phải chạy được lệnh sinh như các đợt trước)
- Modify: `frontend/lib/use-projects.ts` (thêm `useDeleteProject`)
- Create: `frontend/components/projects/delete-project-dialog.tsx` (+ `delete-project-dialog.test.tsx`)
- Modify: `frontend/app/(app)/admin/projects/page.tsx` (+ `page.test.tsx`): tab + nút
- Modify: `frontend/messages/vi.json` (khối `projects`, và chữ lưu trữ ở trang Cài đặt: `archive`, `archiveConfirmTitle`, `archiveConfirm` quanh dòng 226–229)

**Interfaces:**
- Consumes: Task 2 (`DELETE /api/projects/{project_id}` body `{name}` → 204); `useUpdateProject(projectId)` (đã có, nhận `{ archived }`); `useProjects()`.
- Produces:
  - `useDeleteProject(projectId: string)` trong `use-projects.ts`: `mutateAsync(name: string): Promise<void>`, `onSuccess` làm mới `PROJECTS_KEY`.
  - `DeleteProjectDialog({ project }: { project: Project })`: nút "Xoá vĩnh viễn" mở hộp thoại; ô gõ tên; nút Xoá `disabled` tới khi `input.trim() === project.name`; sau khi xoá thành công đóng hộp thoại, toast `common.saved`-kiểu thông báo; lỗi thì `toast.error`.

- [x] **Step 1: Viết test đỏ** `delete-project-dialog.test.tsx` (mock `@/lib/use-projects` như `page.test.tsx`): (a) nút Xoá bị khoá khi ô trống và khi gõ sai tên, mở khoá khi gõ đúng tên (kể cả thừa khoảng trắng); (b) bấm Xoá gọi `mutateAsync("Dự án A")` đúng một lần; (c) lỗi từ `mutateAsync` → `toast.error` và hộp thoại vẫn mở; (d) có câu giải thích "chỉ xoá khỏi app, file Google Sheet và issue GitHub vẫn còn" (chuỗi do bạn đặt trong `vi.json`, test kiểm tra đúng chuỗi đó).
- [x] **Step 2: Mở rộng `page.test.tsx`** (mock `useProjects` trả 2 dự án: một đang dùng, một `archived: true`; mock thêm `useDeleteProject`): (a) mặc định chỉ thấy dự án đang dùng, tab "Đang dùng (1)" và "Thùng rác (1)"; (b) bấm tab Thùng rác thì chỉ thấy dự án đã lưu trữ; (c) nút "Chuyển vào thùng rác" của dự án đang dùng gọi `update` với `{ archived: true }`; (d) tab Thùng rác: "Khôi phục" gọi `update` với `{ archived: false }` và có nút "Xoá vĩnh viễn"; (e) thùng rác trống hiện câu "Thùng rác trống". Các test cũ về `StorageSelect` giữ nguyên và vẫn phải qua.
- [x] **Step 3: Chạy** `cd frontend && npx vitest run components/projects "app/(app)/admin/projects"`. Expected: FAIL (thiếu component/hook/chuỗi).
- [x] **Step 4: Sinh lại API** `npm run gen:api` (route DELETE mới xuất hiện trong `schema.d.ts`); thêm `useDeleteProject` trong `use-projects.ts` theo mẫu `useUpdateProject` (`api.DELETE("/api/projects/{project_id}", { params: { path }, body: { name } })`, dùng `unwrap`).
- [x] **Step 5: Cài `DeleteProjectDialog`** (dùng `Dialog`, `Input`, `Button`, `Label` có sẵn trong `components/ui`) và sửa `admin/projects/page.tsx`: state `tab: "active" | "trash"`; hai nút chuyển tab có `aria-pressed`, hiện số lượng; tab Đang dùng thêm cột/nút "Chuyển vào thùng rác" (gọi `useUpdateProject(project.id)`, `toast.error` khi lỗi); tab Thùng rác có "Khôi phục" và `DeleteProjectDialog`. Component hàng cần hook theo `project.id` nên tách thành component con (như `StorageSelect`). Thêm chuỗi tiếng Việt vào khối `projects` của `vi.json` và đổi chữ ở trang Cài đặt: "Lưu trữ dự án" → "Chuyển vào thùng rác", "Bỏ lưu trữ" → "Khôi phục", nội dung xác nhận nhắc "Admin có thể khôi phục hoặc xoá vĩnh viễn ở trang Quản lý dự án". Với `vi.json` và `page.tsx` đang sửa dở của chủ dự án: chỉ stage phần của mình.
- [x] **Step 6: Chạy** `npx vitest run` (cả bộ), `npx tsc --noEmit`, `npx eslint`. Expected: tất cả PASS, không lỗi. Nếu test trang Cài đặt kiểm tra chữ cũ ("Lưu trữ dự án"/"Bỏ lưu trữ") thì cập nhật theo chữ mới.
- [x] **Step 7: Cập nhật tiến độ**: đánh `[x]` các step của plan này, thêm dòng "Đợt thùng rác xong" vào `HANDOFF.md` (chỉ dòng của mình), ghi chú "Còn lại: review cả nhánh; sau đó viết plan test tay từ spec `2026-11-18-manual-test-run-design.md`".
- [x] **Step 8: Commit** `feat(frontend): thùng rác dự án và xoá vĩnh viễn ở trang Admin` (chỉ phần của mình), rồi `docs: tiến độ thùng rác dự án`.

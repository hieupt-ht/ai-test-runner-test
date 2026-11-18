# Ảnh/video cho màn hình và trang chi tiết màn hình — kế hoạch

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin/QA Lead gắn ảnh/video cho màn hình; mọi thành viên xem trang chi tiết màn hình (thông tin + ảnh + bảng case); form tạo case hiện ảnh của màn hình đã chọn.

**Architecture:** Backend thêm trường `media` vào `Screen` (cột `media_json` cuối tab `Screens`), kiểm tra link bằng `ensure_own_media` và xoá file bị bỏ bằng janitor có sẵn — y như test case. Frontend dùng lại `MediaPicker`, `MediaLightbox`, `MediaVideo`; thêm component `ScreenMediaStrip` dùng chung cho trang chi tiết và `CaseForm`; route mới `screens/[screenId]` chỉ dùng các query đã có (không thêm lượt đọc Sheet).

**Tech Stack:** Python 3.12 / FastAPI / pydantic / pytest (`uv`); Next.js 16 / React / TanStack Query / next-intl / vitest.

**Spec:** `docs/superpowers/specs/2026-11-18-screen-media-and-detail-design.md`

## Global Constraints

- TDD: viết test, chạy thấy đỏ, rồi mới viết code. Comment và chuỗi lỗi tiếng Việt; lỗi API dạng `{"detail": "<câu tiếng Việt>"}`.
- Cột mới **chỉ nối vào cuối** `SCREEN_COLUMNS` (Sheet cũ tự thêm cột lúc khởi động).
- Không đổi quyền: `MANAGE_SCREENS` vẫn chỉ Admin + QA Lead; tester vẫn chỉ tạo case trên màn hình được giao.
- Ảnh màn hình **không** đưa vào GitHub issue (không sửa `issue_format.py`).
- Tối đa 5 ảnh/video mỗi màn hình (`MediaList`).
- Chuỗi giao diện ở `frontend/messages/vi.json`. Đọc `frontend/AGENTS.md` + `frontend/node_modules/next/dist/docs/` trước khi viết route.
- Sau khi sửa API: `cd frontend && npm run gen:api`.
- Cây làm việc có thay đổi chưa commit của chủ dự án (`media-picker`, `case-form`, `admin/projects/page.tsx`, `create-project-dialog`, `vi.json`, `SETUP.md`): sửa chồng lên, **chỉ stage phần của mình** (`git add -p` hoặc stage đúng file mình tạo). Không push.
- Commit: Conventional Commits, mô tả tiếng Việt, message bằng heredoc Git Bash, kết thúc bằng dòng `Co-Authored-By` theo hướng dẫn phiên.
- Lệnh kiểm tra đầy đủ — backend: `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check`; frontend: `cd frontend && npx vitest run && npm run typecheck && npm run lint`.

## Review Focus

1. Dòng Sheet cũ có ô `media_json` trống → đọc ra `media == []`, không lỗi (test ở Task 1).
2. PATCH màn hình không gửi `media` → giữ nguyên ảnh cũ, không gọi janitor (test ở Task 2).
3. Đang tải ảnh lên trong form màn hình mà bấm Lưu → nút Lưu bị khoá cho tới khi tải xong (test ở Task 3).
4. Mở `/screens/SC-9999` không tồn tại → hiện "Không tìm thấy màn hình" + link quay lại, không trắng trang (test ở Task 4).
5. Màn hình có video Drive → trang chi tiết và `CaseForm` hiện bằng `MediaVideo` (iframe), không dùng thẻ `img` (test ở Task 4).

---

## Đợt 1 — Backend

### Task 1: `Screen.media` lưu vào Sheet và nhận qua API

**Files:**
- Modify: `backend/app/core/models/screen.py`, `backend/app/core/sheets/schema.py:44`, `backend/app/core/repositories/screens.py`, `backend/app/core/services/screens.py`, `backend/app/api/routers/screens.py`
- Test: `backend/tests/test_screens_api.py`

**Interfaces:**
- Produces:
  - `Screen.media: MediaList = Field(default_factory=list)` (import `MediaList` từ `app.core.models.media`).
  - `SCREEN_COLUMNS` thêm `"media_json"` ở cuối.
  - `ScreenRepository.create(..., media: list[Media] | None = None)`.
  - `class InvalidScreenError(ValueError)` trong `app/core/services/screens.py`.
  - `ScreenService.__init__(screens, assignments, test_cases, audit_log, *, cloud_name: str = "", drive_enabled: bool = False, janitor: MediaDeleter | None = None)` (`MediaDeleter` từ `app.core.services.evidence_retention`).
  - `ScreenService.create_screen(..., media: list[Media] | None = None)`, `update_screen(..., media: list[Media] | None = None)`; cả hai gọi `ensure_own_media` trước khi ghi, `ForeignMediaError` → `InvalidScreenError(str(error))`.
  - `CreateScreenRequest.media: MediaList = []`, `UpdateScreenRequest.media: MediaList | None = None`; router truyền `cloud_name=services.cloud_name, drive_enabled=services.drive is not None, janitor=services.media_janitor` vào `ScreenService`; `InvalidScreenError` → 422.

- [x] **Step 1: Viết test đỏ** trong `test_screens_api.py` (dùng `media_json(cloud)` giống `test_test_cases_api.py:406`):

```python
def test_screen_media_saved_and_returned(app, client_as_qa_lead, project) -> None:
    app.state.services.cloud_name = "mine"
    created = client_as_qa_lead.post(screens_url(project), json=login_screen(media=[media_json("mine")]))
    assert created.status_code == 201
    assert created.json()["media"][0]["public_id"] == "a"
    listed = client_as_qa_lead.get(screens_url(project)).json()
    assert listed[0]["media"][0]["public_id"] == "a"

def test_screen_media_from_foreign_cloud_is_422(app, client_as_qa_lead, project) -> None:
    app.state.services.cloud_name = "mine"
    response = client_as_qa_lead.post(screens_url(project), json=login_screen(media=[media_json("other")]))
    assert response.status_code == 422
    assert "không thuộc kho lưu trữ" in response.json()["detail"]

def test_screen_more_than_five_media_is_422(app, client_as_qa_lead, project) -> None:
    app.state.services.cloud_name = "mine"
    assert client_as_qa_lead.post(screens_url(project), json=login_screen(media=[media_json("mine")] * 6)).status_code == 422

def test_old_screen_row_without_media_reads_empty(client_as_qa_lead, project, gateway) -> None:
    # Giả lập dòng của Sheet cũ: thêm thẳng một dòng chỉ có 7 cột đầu (không có ô media_json)
    gateway.data[project.spreadsheet_id]["Screens"].append(
        ["SC-0001", "Cũ", "", "/old", "[]", "2026-11-01T00:00:00+00:00", ""]
    )
    listed = client_as_qa_lead.get(screens_url(project)).json()
    assert listed[0]["id"] == "SC-0001"
    assert listed[0]["media"] == []
```

Test cũ `test_tester_can_view_but_not_create` giữ nguyên (tester vẫn 403).

- [x] **Step 2: Chạy thấy đỏ** — `cd backend && uv run pytest tests/test_screens_api.py -q` → FAIL (`media` không có trong response / 201 thay vì 422).
- [x] **Step 3: Viết code** theo Interfaces. Repository: `"media_json": json.dumps([m.model_dump(mode="json") for m in screen.media], ensure_ascii=False)`; đọc `[Media(**item) for item in json.loads(record["media_json"] or "[]")]` (giống `repositories/test_cases.py:81,111`). `update_screen` thêm `"media": media` vào `changes` (giá trị `None` = giữ nguyên, như các trường khác).
- [x] **Step 4: Chạy thấy xanh** — `uv run pytest tests/test_screens_api.py tests/test_assignment_races.py tests/test_sheet_list_cache.py -q` → PASS.
- [x] **Step 5: Commit** — `feat(backend): màn hình có ảnh/video tham khảo (cột media_json)`.

### Task 2: Xoá file khi bỏ ảnh khỏi màn hình hoặc xoá màn hình

**Files:**
- Modify: `backend/app/core/services/screens.py`
- Test: `backend/tests/test_screens_api.py`

**Interfaces:**
- Consumes: `ScreenService(..., janitor=...)` từ Task 1; `janitor.delete(items: list[Media]) -> None`.
- Produces: `update_screen` gọi `janitor.delete(<ảnh cũ có public_id không còn trong bản mới>)` khi `media` được gửi; `delete_screen` lấy màn hình (trong khoá), xoá xong thì `janitor.delete(screen.media)`. Không có janitor thì bỏ qua.

- [x] **Step 1: Viết test đỏ** (janitor giả giống `test_agent_results_api.py:539`, gán vào `app.state.services.media_janitor`):

```python
def test_removing_screen_media_deletes_file(app, client_as_qa_lead, project) -> None:
    # tạo màn hình với ảnh public_id "a" và "b"; PATCH media chỉ còn "b"
    assert deleted == ["a"]

def test_patch_without_media_keeps_files(app, client_as_qa_lead, project) -> None:
    # tạo màn hình có ảnh "a"; PATCH {"name": "Mới"}
    assert deleted == []
    assert response.json()["media"][0]["public_id"] == "a"

def test_deleting_screen_deletes_its_media(app, client_as_qa_lead, project) -> None:
    # tạo màn hình có ảnh "a"; DELETE → 204
    assert deleted == ["a"]

def test_screen_blocked_from_delete_keeps_media(app, client_as_qa_lead, project, ...) -> None:
    # màn hình có test case → DELETE 409
    assert deleted == []
```

- [x] **Step 2: Chạy thấy đỏ** — `uv run pytest tests/test_screens_api.py -q` → FAIL (`deleted` rỗng).
- [x] **Step 3: Viết code** trong `ScreenService` (hàm riêng `_clean_removed_media(old: Screen, new: Screen)` so theo `public_id`, như `services/test_cases.py:503`).
- [x] **Step 4: Chạy bộ backend đầy đủ** — `uv run pytest -q && uv run mypy app && uv run ruff check` → tất cả PASS, sạch.
- [x] **Step 5: Commit** — `feat(backend): xoá ảnh/video khi bỏ khỏi màn hình hoặc xoá màn hình`.

**Hết đợt 1:** đánh dấu `[x]`, ghi tiến độ vào `HANDOFF.md`, dừng cho chủ dự án `/compact`.

---

## Đợt 2 — Frontend

### Task 3: Form màn hình có ô chọn ảnh/video

**Files:**
- Modify: `frontend/lib/api/schema.d.ts` (chạy `npm run gen:api`), `frontend/components/screens/screen-form-dialog.tsx`, `frontend/messages/vi.json`
- Modify (fixture `Screen` thiếu `media` sau khi gen): mọi chỗ `satisfies Screen` / dựng `Screen` trong test (`screen-form-dialog.test.tsx`, `selectable-screens.test.ts`, `case-form.test.tsx`, …) — thêm `media: []`.
- Test: `frontend/components/screens/screen-form-dialog.test.tsx`

**Interfaces:**
- Consumes: API mới từ Task 1 (`Screen.media`, `ScreenInput.media`).
- Produces: `ScreenFormDialog` gửi `media: Media[]` trong `useSaveScreen().mutateAsync(...)`. Lấy `storage` bằng `useProject(projectId).data?.storage ?? "cloudinary"` (như `case-form.tsx:133`). Nhãn mới `screens.fieldMedia` = "Ảnh/video màn hình", `screens.mediaHint` = "Để tester hình dung màn hình khi viết test case. Có thể dán ảnh (Ctrl+V)."

- [ ] **Step 1: Viết test đỏ** (mock thêm `@/lib/use-projects` → `useProject: () => ({ data: { storage: "cloudinary" } })`; mock `@/components/media/media-picker` thành component giả có nút "Thêm ảnh giả" gọi `onChange([...value, ảnhGiả])` và nút "Đang tải giả" gọi `onBusyChange(true)`):
  - `"hiện ảnh sẵn có khi sửa và gửi media khi lưu"` → `mutateAsync.mock.calls[0][0]` `toMatchObject({ media: [existingMedia, ảnhGiả] })`.
  - `"khoá nút Lưu khi đang tải ảnh lên"` → sau "Đang tải giả", `getByRole("button", { name: "Lưu" })` `toBeDisabled()`.
- [ ] **Step 2: Chạy thấy đỏ** — `cd frontend && npx vitest run components/screens` → FAIL.
- [ ] **Step 3: Viết code** — state `media` (khởi tạo `screen?.media ?? []`, reset khi tạo mới xong), state `uploading`; đặt `MediaPicker` sau ô mô tả; nút Lưu `disabled={saveScreen.isPending || uploading}`; dialog đổi `sm:max-w-lg` → `sm:max-w-2xl` và thân form cuộn được (`max-h-[80dvh] overflow-y-auto`) để vừa màn 1366×768.
- [ ] **Step 4: Chạy thấy xanh** — `npx vitest run && npm run typecheck` → PASS.
- [ ] **Step 5: Commit** — `feat(frontend): form màn hình có ảnh/video tham khảo`.

### Task 4: `ScreenMediaStrip` + trang chi tiết màn hình

**Files:**
- Create: `frontend/components/screens/screen-media-strip.tsx`, `frontend/app/(app)/projects/[projectId]/screens/[screenId]/page.tsx`
- Modify: `frontend/app/(app)/projects/[projectId]/screens/page.tsx` (tên màn hình thành link), `frontend/messages/vi.json`
- Test: `frontend/components/screens/screen-media-strip.test.tsx`, `frontend/app/(app)/projects/[projectId]/screens/[screenId]/page.test.tsx`

**Interfaces:**
- Produces: `export function ScreenMediaStrip({ media }: { media: Media[] })` — hàng ảnh nhỏ; ảnh: `<img src={displayUrl(m)}>` bấm mở `MediaLightbox`; video: `MediaVideo`; `media` rỗng → không render gì (`null`). Task 5 dùng component này.
- Trang chi tiết (client component, bọc `<Suspense>` vì `cacheComponents`, theo mẫu `test-cases/[caseId]/page.tsx`): `useProjectId()`, `useParams<{ screenId: string }>()`, `useScreens`, `useAssignments`, `useTestCases(projectId)`, `useMe`, `useProject`.
  - Không thấy màn hình → `screens.notFound` = "Không tìm thấy màn hình" + link "← Màn hình" về `/projects/<id>/screens`.
  - Đầu trang: mã, tên, route, `@dev_owner`, mô tả, `ScreenMediaStrip`.
  - Nút Sửa (`ScreenFormDialog` với `screen`) khi `permissions` có `MANAGE_SCREENS` và `!project.archived`.
  - Nút "Tạo case" → `/projects/<id>/test-cases/new?screen=<screenId>` khi `selectableScreens(...)` chứa màn hình này, có `EDIT_TEST_CASE` và dự án chưa lưu trữ.
  - Bảng case lọc `case.screen_id === screenId`, sắp theo `id`: cột Mã (link), Tiêu đề, Trạng thái (`CaseStatusBadge`), Mức độ (`testCases.severity.*`), Nền tảng (`testCases.platform.*`); bấm dòng → `router.push` tới case (giống `test-cases/page.tsx:200-207`). Không có case → `screens.noCases` = "Màn hình này chưa có test case nào."
  - Tiêu đề bảng: `screens.casesTitle` = "Test case ({count})".

- [ ] **Step 1: Viết test đỏ**
  - `screen-media-strip.test.tsx`: `"rỗng thì không hiện gì"`; `"bấm ảnh thì mở ảnh lớn"` (thấy `img` trong dialog); `"video Drive hiện bằng iframe"` (`container.querySelector("iframe")` khác null, không có `img`).
  - `page.test.tsx` (mock như `results/page.test.tsx:22-35`, thêm `useParams: () => ({ screenId: mocks.screenId })`):
    - `"hiện thông tin màn hình và chỉ case của màn hình đó"` — có `TC-000001` (SC-0001), không có case của SC-0002.
    - `"không tìm thấy màn hình"` — `screenId = "SC-9999"` → thấy "Không tìm thấy màn hình" và link về danh sách.
    - `"tester chưa được giao không thấy nút Tạo case và Sửa"`; `"QA Lead thấy cả hai"`; `"tester được giao thấy Tạo case với link ?screen=SC-0001"`.
- [ ] **Step 2: Chạy thấy đỏ** — `npx vitest run components/screens "app/(app)/projects"` → FAIL (chưa có file).
- [ ] **Step 3: Viết code** theo Interfaces. Ở `screens/page.tsx`, bọc `screen.name` trong `<Link href={`/projects/${projectId}/screens/${screen.id}`}>`.
- [ ] **Step 4: Chạy thấy xanh** — `npx vitest run && npm run typecheck && npm run lint` → PASS.
- [ ] **Step 5: Commit** — `feat(frontend): trang chi tiết màn hình có ảnh và danh sách test case`.

### Task 5: Form tạo case hiện ảnh của màn hình đã chọn

**Files:**
- Modify: `frontend/components/test-cases/case-form.tsx:291-317`, `frontend/messages/vi.json` (`testCases.form.noScreens`)
- Test: `frontend/components/test-cases/case-form.test.tsx`

**Interfaces:**
- Consumes: `ScreenMediaStrip` (Task 4); `screens` prop đã có trong `CaseForm`.
- Produces: dưới ô chọn màn hình (chỉ khi tạo mới) hiện `<ScreenMediaStrip media={screens.find(s => s.id === screenId)?.media ?? []} />`. Đổi `testCases.form.noScreens` thành "Bạn chưa được giao màn hình nào để viết test case. Hãy nhờ QA Lead giao việc."

- [ ] **Step 1: Viết test đỏ** — `"chọn màn hình có ảnh thì hiện ảnh của màn hình đó"` (`defaultScreenId` là màn hình có 1 ảnh → thấy `img` có `src` của ảnh đó); `"danh sách màn hình trống thì nhắc nhờ QA Lead giao việc"`.
- [ ] **Step 2: Chạy thấy đỏ** — `npx vitest run components/test-cases/case-form` → FAIL.
- [ ] **Step 3: Viết code** theo Interfaces.
- [ ] **Step 4: Chạy cả hai bộ đầy đủ** — backend và frontend (lệnh ở Global Constraints) → tất cả PASS, sạch.
- [ ] **Step 5: Commit** — `feat(frontend): form tạo case hiện ảnh của màn hình đã chọn`.

**Hết đợt 2:** đánh dấu `[x]`, ghi tiến độ (số test) vào `HANDOFF.md`, commit `docs: tiến độ ảnh màn hình và trang chi tiết`, dừng cho chủ dự án. Ghi chú: chưa thử trình duyệt thật (1366×768).

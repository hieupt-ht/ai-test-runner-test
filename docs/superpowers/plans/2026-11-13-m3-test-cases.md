# M3 — Test case: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tester (và QA Lead) viết test case theo chuẩn chung cho từng màn hình, gửi duyệt; QA Lead duyệt hoặc trả lại kèm nhận xét. Hai người sửa cùng một case thì người lưu sau nhận 409 "vui lòng tải lại". Trạng thái việc được giao (`TODO` → `WRITING` → `IN_REVIEW` → `APPROVED`) tự suy ra từ test case. Mọi thay đổi ghi AuditLog và xem được lịch sử trên case.

**Architecture:** Xây trên M2, không đổi kiến trúc. Test case nằm ở tab `TestCases` của Sheet dự án (tab đã được tạo từ M2). `TestCaseRepository` lo đọc/ghi + kiểm tra `version` trong khoá; `TestCaseService` lo quyền theo từng case, chuyển trạng thái, AuditLog và gọi `AssignmentStatusUpdater` để cập nhật cột `status` của `Assignments`. Frontend lọc/tìm/phân trang ở phía trình duyệt (backend trả cả danh sách một lần) để mỗi lần đổi bộ lọc không tốn lượt đọc Google.

**Tech Stack:** Như M2. Không thêm thư viện backend. Frontend không thêm thư viện: kéo thả bước dùng HTML5 drag-and-drop gốc kèm nút lên/xuống (để dùng được bằng bàn phím), thêm `components/ui/textarea.tsx` theo kiểu shadcn.

**Spec:** `docs/superpowers/specs/2026-11-12-ai-test-runner-design.md` (mục 4, 7.5, 7.6, 8.2, 9, 11, 12)

## Global Constraints

- Tiếp tục trên nhánh `feature/m1-foundation` (chủ dự án yêu cầu từ M2). Không merge, không push, không tạo PR.
- Commit theo Conventional Commits, mô tả tiếng Việt có dấu, viết message bằng heredoc trong Git Bash.
- Giữ mọi quy tắc của M1/M2: chỉ `gateway.py` gọi Google; ánh xạ Sheet theo tên cột; chuỗi giao diện nằm trong `frontend/messages/vi.json`; lỗi API là `{"detail": "<câu tiếng Việt>"}`; `mypy --strict`, `ruff check`, TypeScript strict, ESLint sạch.
- Mã test case dạng **`TC-000123`** (6 chữ số), đánh số theo từng dự án, bộ đếm `next_tc_id` ở tab `Meta`, khoá `lock:id:<project_id>:tc` (spec 9.3). Không cho sửa mã.
- Trường và giá trị enum đúng spec 7.6: `severity` ∈ `LOW`/`MEDIUM`/`HIGH`; `priority` ∈ `P1`/`P2`/`P3`; `status` ∈ `DRAFT`/`IN_REVIEW`/`APPROVED`/`DEPRECATED`; `version` bắt đầu từ 1, tăng 1 mỗi lần ghi; thời gian lưu ISO UTC; `steps` lưu dạng chuỗi JSON `[{"action": "...", "expected": "..."}]`.
- Câu báo xung đột đúng spec 9.4: **`Case này vừa được <tên người sửa> cập nhật. Vui lòng tải lại.`** (tên lấy từ tab `Users`, không có thì dùng email). Phản hồi 409 kèm bản mới nhất ở khoá `latest`.
- Khoá: tạo case dùng khoá cả tab `lock:<project_id>:test-cases`; sửa case dùng khoá theo bản ghi `lock:<project_id>:test-case:<id>` (spec 9.4; tab TestCases không bao giờ xoá dòng nên dòng không dịch chỗ). TTL theo mặc định của `redis_lock` (60 giây, đã nâng ở fix I-1). **Thứ tự khoá khi lồng nhau: `assignments` trước, `test-cases` sau**, không bao giờ ngược lại.
- Mỗi thao tác ghi case ghi một dòng AuditLog của Sheet dự án, `entity="test_case"`, `entity_id=<TC id>`, `action` ∈ `CREATE`/`UPDATE`/`SUBMIT`/`APPROVE`/`RETURN`/`DEPRECATE`/`RESTORE`.
- Next.js 16: trước khi viết route `test-cases/[caseId]` và đọc `?screen=` đọc `frontend/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/dynamic-routes.md` và `.../04-functions/use-search-params.md` (đang bật `cacheComponents`, `useSearchParams` cần `<Suspense>`).
- Ghi giả định mới vào cuối `DECISIONS.md` (các quyết định đánh dấu **[Quyết định M3]** dưới đây).

**[Quyết định M3]** (ghi vào `DECISIONS.md` ở Task 8):
1. Tester chỉ **tạo** case trên màn hình được giao cho mình; **sửa** được case mình tạo hoặc case thuộc màn hình được giao (spec 4). Bị bỏ giao việc vẫn sửa được case mình tạo.
2. Trạng thái việc tính theo các case **do chính tester đó tạo** trên màn hình đó. Mọi case của tester đều `DEPRECATED` thì coi như `TODO`. M3 chưa có run nên chưa bao giờ ra `TESTED`.
3. Không đổi `screen_id` của case sau khi tạo.
4. Mỗi bước: `action` bắt buộc, `expected` được để trống.
5. Ai có quyền sửa case thì được chuyển case sang `DEPRECATED`; chỉ QA Lead/Admin khôi phục, khôi phục về `DRAFT`.
6. Không xoá màn hình đang có test case (kể cả case đã `DEPRECATED`).
7. Mọi thao tác chuyển trạng thái cũng gửi `version` và cũng bị kiểm tra xung đột.
8. Lọc, tìm, phân trang làm ở trình duyệt; tìm không phân biệt hoa thường và dấu tiếng Việt.

## Review Focus

1. **Duyệt bằng version cũ**: QA Lead mở case, tester sửa nội dung, QA Lead bấm "Duyệt" với version cũ → 409 kèm bản mới, case không được duyệt mà chưa ai đọc nội dung mới. Test ở Task 3 (`test_approve_with_stale_version_is_conflict`).
2. **Tester sửa case không phải của mình, trên màn hình không được giao** → 403; tester bị bỏ giao việc vẫn sửa case mình tạo. Test ở Task 3 (`test_tester_edit_rules`).
3. **Tìm không dấu**: gõ `dang nhap` tìm ra "Đăng nhập", gõ `tc-000012` tìm ra `TC-000012`. Test ở Task 6.
4. **Hai case cùng màn hình đổi trạng thái gần như cùng lúc**: trạng thái việc cuối cùng phải đúng với dữ liệu cuối cùng, không bị lần tính cũ ghi đè. Test ở Task 2 (`test_refresh_reads_cases_inside_lock`, dùng móc `after_next_read`).
5. **Màn hình bị xoá / không tồn tại**: tạo case trên màn hình không có → 422 "Không tìm thấy màn hình"; xoá màn hình đang có case → 409. Test ở Task 3 và Task 5.

---

## File Structure

```
backend/app/
├── core/
│   ├── ids.py                            # + tham số digits
│   ├── models/test_case.py               # TestStep, TestCase, enum, giới hạn độ dài
│   ├── assignment_status.py              # derive_assignment_status(), AssignmentStatusUpdater
│   ├── repositories/test_cases.py        # TestCaseRepository, VersionConflictError
│   ├── repositories/audit_log.py         # + list_for(), AuditEntry
│   ├── repositories/assignments.py       # create(..., status=)
│   └── services/test_cases.py            # TestCaseService
│       services/screens.py  assignments.py   # chặn xoá màn hình có case; trạng thái ban đầu khi giao việc
└── api/
    ├── project_scope.py                  # + test_cases
    └── routers/test_cases.py             # endpoints; routers/me.py: + case_counts
frontend/
├── components/ui/textarea.tsx
├── components/test-cases/                # status-badge, filters-bar, steps-editor, case-form, review-actions,
│                                         # history-panel, conflict-dialog
├── app/(app)/projects/[projectId]/test-cases/page.tsx  new/page.tsx  [caseId]/page.tsx
└── lib/test-cases/                       # filter.ts, steps.ts, actions.ts, conflict.ts, form-schema.ts (+ .test.ts)
    lib/use-test-cases.ts                 # hooks TanStack Query
```

---

### Task 1: Model test case và TestCaseRepository có kiểm tra version

**Files:**
- Create: `backend/app/core/models/test_case.py`, `backend/app/core/repositories/test_cases.py`, `backend/tests/test_test_case_repository.py`
- Modify: `backend/app/core/ids.py`, `backend/tests/test_ids.py`

**Interfaces:**
- Consumes: `IdGenerator`, `SheetTable`, `redis_lock`, `TEST_CASES_TAB`/`TEST_CASE_COLUMNS` (M2).
- Produces:
  ```python
  IdGenerator.next_id(self, entity: str, prefix: str, *, digits: int = 4) -> str   # next_id("tc", "TC", digits=6) -> "TC-000001"

  class Severity(StrEnum): LOW; MEDIUM; HIGH
  class Priority(StrEnum): P1; P2; P3
  class TestCaseStatus(StrEnum): DRAFT; IN_REVIEW; APPROVED; DEPRECATED
  class TestStep(BaseModel): action: str; expected: str          # action 1..500, expected 0..500, bỏ khoảng trắng hai đầu
  class TestCaseContent(BaseModel):                                # phần người dùng nhập
      title: str            # 1..200
      precondition: str     # 0..2000, mặc định ""
      test_data: str        # 0..2000, mặc định ""
      steps: list[TestStep] # 1..50
      expected_result: str  # 1..2000
      severity: Severity; priority: Priority
  class TestCase(TestCaseContent):
      id: str; screen_id: str; status: TestCaseStatus
      created_by: str; updated_by: str; created_at: datetime; updated_at: datetime; version: int

  class TestCaseNotFoundError(Exception): ...
  class VersionConflictError(Exception):
      latest: TestCase          # bản đang có trên Sheet
  class TestCaseRepository:
      def __init__(self, gateway, spreadsheet_id: str, redis: Redis, project_id: str, *,
                   lock_wait_seconds: float = 5.0) -> None
      def list_all(self) -> list[TestCase]                    # sắp theo id
      def get(self, case_id: str) -> TestCase | None
      def create(self, *, screen_id: str, content: TestCaseContent, actor: str) -> TestCase
      # status DRAFT, version 1, created_by = updated_by = actor; append trong khoá lock:<pid>:test-cases
      def save(self, case: TestCase, *, expected_version: int, actor: str) -> TestCase
      # trong khoá lock:<pid>:test-case:<id>: tìm dòng theo cột id (find_row_number), đọc dòng đó,
      # version trên Sheet != expected_version → VersionConflictError(bản trên Sheet);
      # khớp → ghi case với version = expected_version + 1, updated_by = actor, updated_at = utc_now()
      # không có dòng → TestCaseNotFoundError
  ```
- Không cache test case (spec 9.7).

- [ ] **Step 1: Test**
  ```python
  # test_ids.py
  def test_digits_controls_padding() -> None:   # next_id("tc", "TC", digits=6) == "TC-000001"; Meta có next_tc_id = 2

  # test_test_case_repository.py (dùng FakeSheetsGateway + Sheet dự án đã bootstrap, lock_wait 0.1)
  def test_create_starts_as_draft_version_1(repo) -> None:
      # id "TC-000001", status DRAFT, version 1, created_by == updated_by == "an@x.com";
      # ô steps trên Sheet là JSON '[{"action": "Mở trang", "expected": "Thấy form"}]' (ensure_ascii=False)
  def test_round_trip_keeps_vietnamese_and_step_order(repo) -> None: ...
  def test_save_with_matching_version_increments(repo) -> None:     # version 1 → 2, updated_by đổi
  def test_save_with_stale_version_raises_conflict(repo) -> None:
      # A và B cùng đọc version 1; A save OK (version 2); B save expected_version=1 →
      # VersionConflictError, error.latest.version == 2, error.latest.updated_by == A; Sheet giữ nội dung của A
  def test_save_unknown_case_raises(repo) -> None: ...
  def test_parallel_creates_get_distinct_ids(repo_factory) -> None:
      # 2 thread × 5 lần create, mỗi thread một repository riêng → 10 id khác nhau, 10 dòng (spec 9.9)
  ```
- [ ] **Step 2:** `cd backend && uv run pytest tests/test_ids.py tests/test_test_case_repository.py -q`. Kỳ vọng: FAIL (chưa có module / chưa có `digits`).
- [ ] **Step 3:** Cài đặt. `version` đọc từ Sheet bằng `int(...)`.
- [ ] **Step 4:** `uv run pytest -q && uv run mypy app tests && uv run ruff check .`. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(core): thêm lưu trữ test case có kiểm tra version`.

---

### Task 2: Trạng thái việc tự suy ra từ test case

**Files:**
- Create: `backend/app/core/assignment_status.py`, `backend/tests/test_assignment_status.py`
- Modify: `backend/app/core/repositories/assignments.py` (`create(..., status: AssignmentStatus = AssignmentStatus.TODO)`)

**Interfaces:**
- Consumes: `TestCase`, `TestCaseStatus`, `TestCaseRepository` (Task 1); `AssignmentRepository.lock()/list_all()/update()` (M2).
- Produces:
  ```python
  def derive_assignment_status(cases: list[TestCase], *, screen_id: str, tester_email: str,
                               tested_case_ids: frozenset[str] = frozenset()) -> AssignmentStatus
  # chỉ xét case có screen_id và created_by == tester_email, bỏ DEPRECATED:
  # rỗng → TODO; có DRAFT → WRITING; không DRAFT mà có IN_REVIEW → IN_REVIEW;
  # còn lại (toàn APPROVED) → TESTED nếu mọi id nằm trong tested_case_ids, ngược lại APPROVED

  class AssignmentStatusUpdater:
      def __init__(self, assignments: AssignmentRepository, test_cases: TestCaseRepository) -> None
      def refresh_screen(self, screen_id: str) -> None
      # trong assignments.lock(): đọc lại test case và assignment, chỉ update dòng có status đổi
  ```

- [ ] **Step 1: Test**
  ```python
  @pytest.mark.parametrize(("statuses", "expected"), [
      ([], "TODO"),
      (["DEPRECATED"], "TODO"),
      (["DRAFT", "APPROVED"], "WRITING"),
      (["IN_REVIEW", "APPROVED"], "IN_REVIEW"),
      (["APPROVED", "APPROVED", "DEPRECATED"], "APPROVED"),
  ])
  def test_derive_status(statuses, expected) -> None: ...   # case của tester, cùng màn hình
  def test_only_counts_this_testers_cases_on_this_screen() -> None:
      # case DRAFT của người khác, và case DRAFT của tester ở màn hình khác → vẫn TODO
  def test_tested_when_all_approved_cases_have_results() -> None:   # tested_case_ids đủ → TESTED; thiếu 1 → APPROVED
  def test_refresh_updates_only_changed_rows(gateway, ...) -> None:
      # 2 tester cùng màn hình; chỉ tester A có case DRAFT → A WRITING, B vẫn TODO; gateway.calls chỉ có 1 "update:Assignments!"
  def test_refresh_reads_cases_inside_lock(gateway, ...) -> None:
      # móc after_next_read["TestCases"] của lần refresh thứ nhất chạy một refresh khác (repository riêng);
      # refresh chen vào phải nhận LockTimeout (bỏ qua bằng suppress), tức là lần đọc TestCases nằm trong khoá
  ```
- [ ] **Step 2:** `uv run pytest tests/test_assignment_status.py -q`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** pytest, mypy, ruff. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(core): tự suy ra trạng thái việc được giao từ test case`.

---

### Task 3: TestCaseService — quyền theo case, chuyển trạng thái, AuditLog

**Files:**
- Create: `backend/app/core/services/test_cases.py`, `backend/tests/test_test_case_service.py`
- Modify: `backend/app/core/repositories/audit_log.py` (+ `list_for`, `AuditEntry`), `backend/tests/test_audit_log_repository.py`

**Interfaces:**
- Consumes: Task 1, Task 2; `can()`/`Action.EDIT_TEST_CASE`/`Action.REVIEW_TEST_CASE`; `ScreenRepository.get`; `ProjectMemberRepository.is_member`; `AssignmentRepository.list_all`.
- Produces:
  ```python
  class AuditEntry(BaseModel): at: datetime; actor: str; action: str; diff: dict[str, Any]
  AuditLogRepository.list_for(self, entity: str, entity_id: str) -> list[AuditEntry]   # mới nhất trước

  class CaseAction(StrEnum): SUBMIT; APPROVE; RETURN; DEPRECATE; RESTORE
  class InvalidTestCaseError(Exception): ...      # 422, str() là câu tiếng Việt
  class TestCasePermissionError(Exception): ...   # 403
  class InvalidTransitionError(Exception): ...    # 409, str() là câu tiếng Việt

  class TestCaseService:
      def __init__(self, *, project_id: str, test_cases: TestCaseRepository, screens: ScreenRepository,
                   assignments: AssignmentRepository, members: ProjectMemberRepository,
                   status_updater: AssignmentStatusUpdater, audit_log: AuditLogRepository) -> None
      def list_cases(self) -> list[TestCase]
      def get_case(self, case_id: str) -> TestCase                 # TestCaseNotFoundError
      def can_edit(self, user: User, case: TestCase) -> bool
      def can_review(self, user: User) -> bool
      def create(self, user: User, *, screen_id: str, content: TestCaseContent) -> TestCase
      def update_content(self, user: User, case_id: str, *, version: int,
                         content: TestCaseContent) -> TestCase
      def transition(self, user: User, case_id: str, action: CaseAction, *, version: int,
                     comment: str = "") -> TestCase
      def history(self, case_id: str) -> list[AuditEntry]
  ```
- Quy tắc:
  - Quyền sửa (`update_content`, `SUBMIT`, `DEPRECATE`): `can(user, EDIT_TEST_CASE, is_member=..., owns_or_assigned=case.created_by == user.email or <user được giao case.screen_id>)`. Tạo: `owns_or_assigned = <user được giao screen_id>`. Duyệt (`APPROVE`, `RETURN`, `RESTORE`): `can(user, REVIEW_TEST_CASE, is_member=...)`. Không đủ → `TestCasePermissionError`.
  - Chuyển trạng thái hợp lệ: `SUBMIT` DRAFT→IN_REVIEW; `APPROVE` IN_REVIEW→APPROVED; `RETURN` IN_REVIEW→DRAFT (comment sau khi strip phải 1..1000 ký tự, thiếu → `InvalidTestCaseError("Trả lại phải kèm nhận xét")`); `DEPRECATE` mọi trạng thái trừ DEPRECATED → DEPRECATED; `RESTORE` DEPRECATED→DRAFT. Sai → `InvalidTransitionError(f"Không thể thực hiện thao tác này khi case đang ở trạng thái {status}")`.
  - `update_content`: case `DEPRECATED` → `InvalidTransitionError("Case đã ngừng dùng, hãy khôi phục trước khi sửa")`; nội dung không đổi → trả case hiện tại, không ghi; có đổi và case đang `IN_REVIEW`/`APPROVED` → về `DRAFT`.
  - `create`: màn hình không có → `InvalidTestCaseError("Không tìm thấy màn hình")`.
  - Sau mỗi lần ghi: ghi AuditLog (diff: CREATE = toàn bộ case; UPDATE = `{field: [cũ, mới]}`; chuyển trạng thái = `{"status": [cũ, mới]}`, RETURN thêm `"comment"`), rồi `status_updater.refresh_screen(case.screen_id)`.
  - `VersionConflictError` từ repository đi thẳng lên (router xử lý).

- [ ] **Step 1: Test** (dựng service trực tiếp như `test_assignment_races.py`; lead, tester A được giao SC-0001, tester B không được giao)
  ```python
  def test_tester_creates_case_on_assigned_screen_and_assignment_becomes_writing(...) -> None
  def test_create_on_unknown_screen_is_invalid(...) -> None          # "Không tìm thấy màn hình"
  def test_tester_edit_rules(...) -> None:
      # B sửa case của A ở SC-0001 → TestCasePermissionError; B tạo case trên SC-0001 → TestCasePermissionError;
      # bỏ giao việc của A (xoá assignment) → A vẫn sửa được case mình tạo
  def test_full_review_flow(...) -> None:
      # A tạo → SUBMIT → assignment IN_REVIEW; lead APPROVE → assignment APPROVED; version tăng 1 mỗi bước
  def test_return_requires_comment_and_is_in_history(...) -> None:
      # RETURN với comment "  " → InvalidTestCaseError; với "Thiếu bước đăng xuất" → DRAFT,
      # history()[0].action == "RETURN" và diff["comment"] == "Thiếu bước đăng xuất"
  def test_editing_approved_case_moves_it_back_to_draft(...) -> None
  def test_unchanged_content_does_not_write(...) -> None             # version giữ nguyên, không có dòng AuditLog mới
  def test_invalid_transitions(...) -> None                          # APPROVE khi DRAFT, RESTORE khi DRAFT, sửa khi DEPRECATED
  def test_tester_cannot_approve_or_restore(...) -> None
  def test_approve_with_stale_version_is_conflict(...) -> None:
      # lead đọc version 2 (IN_REVIEW); A sửa nội dung (version 3, về DRAFT); lead APPROVE version=2 → VersionConflictError;
      # case vẫn DRAFT
  def test_deprecate_and_restore(...) -> None                         # A deprecate case mình; lead restore → DRAFT
  ```
  `test_audit_log_repository.py`: `test_list_for_filters_and_sorts_newest_first`.
- [ ] **Step 2:** `uv run pytest tests/test_test_case_service.py tests/test_audit_log_repository.py -q`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** pytest, mypy, ruff. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(core): thêm nghiệp vụ test case, gửi duyệt và duyệt`.

---

### Task 4: API test case và phản hồi 409 có bản mới nhất

**Files:**
- Create: `backend/app/api/routers/test_cases.py`, `backend/tests/test_test_cases_api.py`
- Modify: `backend/app/api/project_scope.py` (+ `test_cases: TestCaseRepository`), `backend/app/main.py` (gắn router)

**Interfaces:**
- Consumes: Task 3; `load_project`, `scope_for` (M2).
- Produces (prefix `/api/projects/{project_id}/test-cases`):
  ```python
  class TestCaseDetail(TestCase): can_edit: bool; can_review: bool
  class ConflictResponse(BaseModel): detail: str; latest: TestCase
  class CreateTestCaseRequest(TestCaseContent): screen_id: str
  class UpdateTestCaseRequest(TestCaseContent): version: int
  class TransitionRequest(BaseModel): version: int; comment: str = ""
  ```
  - `GET ""` (VIEW_PROJECT) → `list[TestCase]` (gồm cả DEPRECATED).
  - `POST ""` (EDIT_TEST_CASE) → 201 `TestCase`.
  - `GET /{case_id}` (VIEW_PROJECT) → `TestCaseDetail`; không có → 404 "Không tìm thấy test case".
  - `PUT /{case_id}` (EDIT_TEST_CASE) body `UpdateTestCaseRequest` → `TestCase`.
  - `POST /{case_id}/submit|approve|return|deprecate|restore` body `TransitionRequest` → `TestCase`. Action ở `load_project`: `EDIT_TEST_CASE` cho submit/deprecate, `REVIEW_TEST_CASE` cho approve/return/restore.
  - `GET /{case_id}/history` (VIEW_PROJECT) → `list[AuditEntry]`.
  - Ánh xạ lỗi: `InvalidTestCaseError` 422; `TestCasePermissionError` 403 "Bạn không có quyền thực hiện thao tác này"; `InvalidTransitionError` 409; `TestCaseNotFoundError` 404; `LockTimeout` 409 "Dữ liệu đang được cập nhật, vui lòng thử lại"; `VersionConflictError` → `JSONResponse(409, ConflictResponse(detail="Case này vừa được <tên> cập nhật. Vui lòng tải lại.", latest=...))`. Khai báo `responses={409: {"model": ConflictResponse}}` trên PUT và các POST chuyển trạng thái để frontend có kiểu.

- [ ] **Step 1: Test**
  ```python
  def test_tester_creates_lists_and_reads_case(...) -> None   # GET /{id}: can_edit True, can_review False
  def test_two_people_save_same_version_second_gets_409(...) -> None:
      # spec 9.9: An và Bình (đều được giao SC-0001) cùng PUT version 1; An 200 (version 2);
      # Bình 409, detail == "Case này vừa được An cập nhật. Vui lòng tải lại.", latest.version == 2
  def test_validation_errors_are_422(...) -> None:   # steps [], step action "", severity "URGENT", title "" → 422
  def test_lead_returns_case_with_comment_and_history_shows_it(...) -> None
  def test_viewer_can_read_but_not_create(...) -> None   # GET 200, POST 403
  def test_non_member_gets_404(...) -> None
  def test_archived_project_rejects_writes(...) -> None  # 409 "Dự án đã được lưu trữ"
  def test_parallel_creates_via_api_get_distinct_ids(...) -> None:
      # 2 thread, mỗi thread một TestClient đã đăng nhập, mỗi thread POST 3 case → 6 id khác nhau (spec 9.9)
  ```
- [ ] **Step 2:** `uv run pytest tests/test_test_cases_api.py -q`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Cài đặt. Tên người sửa lấy qua `services.users.get(latest.updated_by)`.
- [ ] **Step 4:** pytest, mypy, ruff. Kỳ vọng: PASS. `cd ../frontend && npm run gen:api`, kiểm tra `lib/api/schema.d.ts` có `ConflictResponse`.
- [ ] **Step 5:** Commit `feat(api): thêm API test case và báo xung đột khi lưu`.

---

### Task 5: Nối test case vào màn hình, giao việc và "Việc của tôi"

**Files:**
- Modify: `backend/app/core/services/screens.py`, `backend/app/core/services/assignments.py`, `backend/app/api/routers/screens.py`, `backend/app/api/routers/assignments.py`, `backend/app/api/routers/me.py`, `backend/app/core/models/assignment.py`, `backend/tests/test_screens_api.py`, `backend/tests/test_assignments_api.py`

**Interfaces:**
- Consumes: Task 1, Task 2.
- Produces:
  ```python
  class ScreenHasTestCasesError(Exception): ...     # router → 409 "Màn hình đang có test case, không xoá được"
  ScreenService.__init__(self, screens, assignments, test_cases: TestCaseRepository, audit_log)
  AssignmentService.__init__(..., test_cases: TestCaseRepository, ...)
  MyAssignment.case_counts: dict[TestCaseStatus, int]   # case của chính user trên màn hình đó, đủ 4 khoá, mặc định 0
  ```
- `delete_screen`: trong `assignments.lock()` (giữ nguyên), kiểm tra thêm có case nào `screen_id` đó → `ScreenHasTestCasesError`.
- `assign`: trạng thái ban đầu của việc mới = `derive_assignment_status(<case hiện có>, ...)` (tester có thể đã có case trên màn hình từ lần giao trước).
- `me.py`: mỗi dự án đọc thêm tab TestCases một lần; lỗi Sheet vẫn bỏ qua dự án như fix I-5.

- [ ] **Step 1: Test**
  ```python
  def test_delete_screen_with_test_case_is_409(...) -> None
  def test_reassign_tester_keeps_derived_status(...) -> None:
      # A có case DRAFT trên SC-0001; bỏ giao rồi giao lại → assignment mới có status WRITING
  def test_my_assignments_include_case_counts(...) -> None:
      # A có 2 DRAFT + 1 IN_REVIEW trên SC-0001 → case_counts == {"DRAFT": 2, "IN_REVIEW": 1, "APPROVED": 0, "DEPRECATED": 0}, status WRITING
  ```
- [ ] **Step 2:** `uv run pytest tests/test_screens_api.py tests/test_assignments_api.py -q`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** pytest, mypy, ruff. Kỳ vọng: PASS, kể cả `test_assignment_races.py`. `npm run gen:api`.
- [ ] **Step 5:** Commit `feat(api): nối test case với màn hình, giao việc và Việc của tôi`.

---

### Task 6: Frontend — logic thuần và danh sách test case

**Files:**
- Create: `frontend/lib/test-cases/filter.ts` (+ `.test.ts`), `frontend/lib/test-cases/actions.ts` (+ `.test.ts`), `frontend/lib/use-test-cases.ts`, `frontend/components/test-cases/status-badge.tsx`, `frontend/components/test-cases/filters-bar.tsx`, `frontend/app/(app)/projects/[projectId]/test-cases/page.tsx`
- Modify: `frontend/lib/api/types.ts` (TestCase, TestCaseDetail, TestStep, TestCaseStatus, Severity, Priority, AuditEntry, ConflictResponse), `frontend/lib/project-tabs.ts` (+ tab `test-cases`, VIEW_PROJECT, đứng sau `screens`), `frontend/lib/project-tabs.test.ts`, `frontend/messages/vi.json`

**Interfaces:**
- Produces:
  ```ts
  export type CaseFilters = { screenId?: string; status?: TestCaseStatus; severity?: Severity;
                              priority?: Priority; createdBy?: string; query: string }
  export function normalizeForSearch(text: string): string   // chữ thường, bỏ dấu (NFD), "đ" → "d", bỏ khoảng trắng thừa
  export function filterTestCases(cases: TestCase[], filters: CaseFilters): TestCase[]
  // query khớp id hoặc title; mặc định (status undefined) ẩn DEPRECATED
  export function paginate<T>(items: T[], page: number, pageSize: number): { items: T[]; pageCount: number }
  export type CaseAction = "submit" | "approve" | "return" | "deprecate" | "restore"
  export function availableActions(status: TestCaseStatus, canEdit: boolean, canReview: boolean): CaseAction[]
  // cùng quy tắc chuyển trạng thái với backend (Task 3)
  export function useTestCases(projectId: string): UseQueryResult<TestCase[]>
  export function useTestCase(projectId: string, caseId: string): UseQueryResult<TestCaseDetail>
  export function useCaseHistory(projectId: string, caseId: string): UseQueryResult<AuditEntry[]>
  ```
- Trang danh sách: bảng (mã, tiêu đề, màn hình, severity, priority, trạng thái, người tạo, cập nhật lúc), 25 dòng/trang, bộ lọc theo `CaseFilters`, ô tìm; `?screen=SC-0001` đặt sẵn bộ lọc màn hình; nút "Tạo test case" khi có `EDIT_TEST_CASE` và dự án chưa lưu trữ; danh sách trống có hướng dẫn bước tiếp theo. Màu trạng thái: DRAFT xám, IN_REVIEW cam, APPROVED xanh lá, DEPRECATED gạch ngang mờ (spec 11).

- [ ] **Step 1: Test (Vitest)**
  ```ts
  it("tìm không dấu và không phân biệt hoa thường", ...)  // "dang nhap" → "Đăng nhập thành công"; "tc-000012" → TC-000012
  it("mặc định ẩn case DEPRECATED, chọn trạng thái DEPRECATED thì hiện", ...)
  it("lọc kết hợp màn hình + severity + người tạo", ...)
  it("paginate chia trang và trả số trang", ...)             // 51 phần tử, 25/trang → 3 trang, trang 3 có 1 phần tử
  it("availableActions theo trạng thái và quyền", ...)
  // ("DRAFT", true, false) → ["submit", "deprecate"]
  // ("IN_REVIEW", true, true) → ["approve", "return", "deprecate"]   (QA Lead: vừa sửa được vừa duyệt được)
  // ("IN_REVIEW", true, false) → ["deprecate"]
  // ("DEPRECATED", true, false) → []; ("DEPRECATED", true, true) → ["restore"]
  it("tab Test case nằm ngay sau Màn hình và có nhãn trong vi.json", ...)
  ```
- [ ] **Step 2:** `cd frontend && npm run test`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Đọc tài liệu Next.js (Global Constraints), rồi cài đặt.
- [ ] **Step 4:** `npm run test && npm run typecheck && npm run lint && npm run build`. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(frontend): thêm danh sách test case có lọc và tìm kiếm`.

---

### Task 7: Frontend — form test case, duyệt, lịch sử, báo xung đột

**Files:**
- Create: `frontend/components/ui/textarea.tsx`, `frontend/lib/test-cases/steps.ts` (+ `.test.ts`), `frontend/lib/test-cases/form-schema.ts` (+ `.test.ts`), `frontend/lib/test-cases/conflict.ts` (+ `.test.ts`), `frontend/components/test-cases/steps-editor.tsx`, `case-form.tsx`, `review-actions.tsx`, `history-panel.tsx`, `conflict-dialog.tsx`, `frontend/app/(app)/projects/[projectId]/test-cases/new/page.tsx`, `.../test-cases/[caseId]/page.tsx`
- Modify: `frontend/lib/api/client.ts` (`ApiError` thêm `readonly body?: unknown`), `frontend/lib/api/request.ts` (truyền `result.error` vào `ApiError`), `frontend/lib/use-test-cases.ts` (mutations), `frontend/app/(app)/my-work/page.tsx` (hiện `case_counts`, nút "Viết test case" → `/projects/<id>/test-cases?screen=<screen_id>`), `frontend/app/(app)/projects/[projectId]/screens/page.tsx` (số case + link sang danh sách đã lọc), `frontend/messages/vi.json`

**Interfaces:**
- Produces:
  ```ts
  export function moveStep<T>(steps: T[], from: number, to: number): T[]
  export function insertStepAfter(steps: TestStep[], index: number): TestStep[]   // chèn {action:"", expected:""}
  export function removeStep(steps: TestStep[], index: number): TestStep[]        // giữ tối thiểu 1 bước
  export const testCaseFormSchema: z.ZodType<TestCaseContent>   // cùng giới hạn độ dài với backend Task 1
  export function conflictFrom(error: unknown): { message: string; latest: TestCase } | null
  // ApiError status 409 có body.latest → trả về; còn lại null
  export function useCreateTestCase(projectId), useUpdateTestCase(projectId, caseId),
         useTransitionTestCase(projectId, caseId)   // invalidate ["projects", id] và ["me","assignments"]
  ```
- Form: các ô theo spec 7.6; trình soạn bước có kéo thả (HTML5 `draggable`), nút lên/xuống, nút xoá, `Ctrl+Enter` trong ô bước thêm bước mới ngay dưới và đưa con trỏ vào đó. Hai nút rõ ràng: "Lưu nháp" và "Lưu và gửi duyệt" (tạo/sửa rồi gọi submit). Form gửi `version` đang có.
- Trang chi tiết: nội dung case (chỉ đọc nếu `!can_edit`), nút theo `availableActions`; "Trả lại" mở hộp nhập nhận xét bắt buộc; "Ngừng dùng" có hộp xác nhận; case `DRAFT` có lần `RETURN` gần nhất trong lịch sử thì hiện khung nhận xét đó ở đầu trang; khung lịch sử (thời gian, người, hành động, nhận xét).
- 409 có `latest`: `ConflictDialog` hiện câu `detail`, nút "Tải lại" thay dữ liệu form bằng `latest` (mất phần đang sửa, đúng spec 2 và 9.4 "không so sánh hay gộp"). 409 không có `latest` (trạng thái không hợp lệ, đang bận) → toast lỗi.

- [ ] **Step 1: Test (Vitest)**
  ```ts
  it("moveStep đổi chỗ đúng và không sửa mảng gốc", ...)
  it("insertStepAfter chèn bước trống ngay sau vị trí", ...)
  it("removeStep không xoá bước cuối cùng", ...)
  it("schema báo lỗi khi không có bước, action rỗng, tiêu đề quá 200 ký tự", ...)
  it("conflictFrom lấy latest từ ApiError 409", ...)          // ApiError(409, msg, {detail, latest}) → {message, latest}
  it("conflictFrom trả null với 409 không có latest và với lỗi khác", ...)
  ```
- [ ] **Step 2:** `npm run test`. Kỳ vọng: FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** `npm run test && npm run typecheck && npm run lint && npm run build`. Kỳ vọng: PASS.
- [ ] **Step 5:** Commit `feat(frontend): thêm form test case, duyệt và báo xung đột khi lưu`.

---

### Task 8: Quyết định, README, chạy thử toàn bộ

**Files:**
- Modify: `DECISIONS.md` (thêm 8 mục **[Quyết định M3]** ở Global Constraints), `README.md` (mục tính năng: test case, quy trình duyệt, ý nghĩa 409)

- [ ] **Step 1:** Cập nhật `DECISIONS.md` và `README.md`.
- [ ] **Step 2:** Toàn bộ: `cd backend && uv run pytest -q && uv run mypy app tests && uv run ruff check . && cd ../frontend && npm run test && npm run typecheck && npm run lint && npm run build`. Kỳ vọng: PASS.
- [ ] **Step 3:** `docker compose up --build -d`, kiểm tra bằng tay với dự án có sẵn (cần chủ dự án có GitHub App để tạo dự án; nếu chưa có thì ghi rõ bước này **chưa chạy**):
  1. Tester tạo case trên màn hình được giao (3 bước, kéo đổi thứ tự bước 1 và 3), "Lưu và gửi duyệt"; "Việc của tôi" hiện `IN_REVIEW` và số case.
  2. Mở cùng case ở hai trình duyệt (Tester và QA Lead), cùng sửa; người lưu sau thấy "Case này vừa được … cập nhật. Vui lòng tải lại.", bấm "Tải lại" thấy nội dung mới.
  3. QA Lead trả lại kèm nhận xét → Tester thấy nhận xét ở đầu trang; sửa, gửi lại; QA Lead duyệt → việc thành `APPROVED`.
  4. Mở Sheet dự án: tab `TestCases` có dòng, ô `steps` là JSON đọc được tiếng Việt, `AuditLog` có các dòng tương ứng.
- [ ] **Step 4:** Commit `docs: cập nhật quyết định và README cho M3`.

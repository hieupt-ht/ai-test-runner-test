# Nhập test case từ Excel — kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** QA/tester nhập cả file .xlsx test case theo mẫu; tester được giao màn hình chỉ chạy (không sửa) case người khác viết; FAIL bắt buộc có bằng chứng.

**Architecture:** Bộ đọc file là hàm thuần trong `app/core/services/case_import.py` (bytes + màn hình → cases/errors/warnings). Ghi hàng loạt qua `IdGenerator.next_ids` + `TestCaseRepository.create_many` + `AuditLogRepository.record_many` để số lượt gọi Google không phụ thuộc số case. Quyền tách `can_edit` (người tạo / lead) và `can_run` (thêm người được giao màn hình).

**Tech Stack:** FastAPI, openpyxl, pytest + FakeSheetsGateway; Next.js 16, TanStack Query, next-intl, vitest.

**Spec:** `docs/superpowers/specs/2026-11-19-import-test-cases-design.md`

## Global Constraints

- Không push, không tạo PR khi chưa được đồng ý. Không commit thẳng vào `main`. Làm trên `feature/ai-agent-runner`.
- Commit Conventional Commits, type tiếng Anh, nội dung tiếng Việt có dấu, message viết bằng heredoc Git Bash, kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Chỉ `git add` đúng file của task. Cây làm việc có sẵn thay đổi chưa commit của chủ dự án (`SETUP.md`, `frontend/app/(app)/admin/projects/page.tsx`, `media-picker*`, `case-form*`, `frontend/messages/vi.json`, `backend/tests/test_drive_auth.py`, `backend/tests/test_project_repository.py`): không ghi đè. Với `vi.json`/`case-form*` phải `git add -p` chỉ phần mình thêm.
- Không chạy `ruff format` cho cả cây; chỉ format file mình sửa.
- TDD: viết test, xem đỏ, rồi mới code. Comment code tiếng Việt.
- Mỗi task xong chạy: `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check app tests`; task frontend thêm `cd frontend && npx vitest run && npx tsc --noEmit && npx eslint .`.
- Mã màn hình thật trong app là `SC-0001` (spec ghi ví dụ `SCR-0001`): ô "Màn hình" khớp theo **id màn hình**, bất kể tiền tố.
- Câu chữ cố định từ spec (copy đúng):
  - `"File không đúng mẫu, hãy tải file mẫu mới"`
  - `"Có nhiều màn hình tên này, hãy ghi mã màn hình"`
  - `"Bạn chưa được giao màn hình này"`
  - `"Google Sheets đang bận, chưa nhập case nào, hãy thử lại"` (503)
  - `"Có người đang tạo case, hãy thử lại"` (409)
  - `"Kết quả Fail cần ít nhất một ảnh hoặc video bằng chứng"` (422)
  - `"Case do người khác viết, cần sửa hãy báo người viết hoặc QA Lead"`
  - Thông báo: `"Có N case mới cần chạy ở: Đăng nhập, Giỏ hàng"`
- Giới hạn: file ≤ 2 MB (`2 * 1024 * 1024` byte), ≤ 2000 dòng dữ liệu, ≤ 300 case, chỉ `.xlsx`.
- Làm theo đợt, mỗi đợt ghi tiến độ vào plan + `HANDOFF.md` rồi dừng cho /compact: **Đợt 1** Task 1–3, **Đợt 2** Task 4–7, **Đợt 3** Task 8–10.

## Review Focus

1. **File xuất từ Google Sheets**: tên sheet khác `Test case`, ô số (`1`, `2.0`), ô Regression là boolean `True` → phải đọc đúng (sheet đầu tiên, số nguyên in không có `.0`, bool → Có/Không). Test ở Task 4.
2. **File không phải xlsx thật** (đổi đuôi .csv thành .xlsx, file hỏng) → trả một lỗi `row=null` "Không đọc được file .xlsx", không 500. Test ở Task 4 và Task 7.
3. **Tester B gửi kết quả case của A** (được giao cùng màn hình) → 201 và case chuyển `TESTED`, audit `MANUAL_TEST` ghi actor là B. Test ở Task 2.
4. **Màn hình bị xoá giữa preview và import** → import báo lỗi theo dòng (422), không ghi case nào. Test ở Task 6.
5. **Nhập 100 case một màn hình** → số lượt gọi gateway bằng đúng số lượt khi nhập 1 case. Test ở Task 6.

---

## Đợt 1 — Luật trạng thái, quyền chạy, bằng chứng FAIL

> **Tiến độ: XONG (2026-11-19)** — Task 1–3, commit `22cd6ba`, `13b1410`, `6f3aedb`; mỗi task đã qua kiểm tra. Việc còn treo: `me.py` `case_counts` lệch luật mới.

### Task 1: Trạng thái việc đếm mọi case của màn hình

**Files:**
- Modify: `backend/app/core/assignment_status.py:9-43`
- Modify: `backend/tests/test_assignment_status.py`, `backend/tests/test_assignments_api.py`, `backend/tests/test_test_case_service.py` (chỉ những test dựa vào luật "chỉ case của mình")
- Modify: `frontend/messages/vi.json:519` (`"WRITING": "Đang làm"`)

**Interfaces:**
- Produces: `derive_assignment_status(cases, *, screen_id, tester_email, tested_case_ids=frozenset())` giữ nguyên chữ ký; `tester_email` không còn dùng để lọc (giữ tham số để không đổi chỗ gọi; ghi comment "giữ cho tương thích, mọi tester cùng màn hình có chung trạng thái").

- [ ] **Step 1: Viết test đỏ** trong `test_assignment_status.py`:
  - `test_counts_cases_created_by_someone_else`: một case `created_by="lead@x.com"`, `DRAFT`, Manual, cùng `screen_id` → `derive(..., tester_email="an@x.com") == AssignmentStatus.WRITING`; đổi sang `TESTED` → `TESTED`.
  - `test_testers_on_same_screen_share_status`: case do `a@x.com` tạo, `TESTED` Manual → cả `a@x.com` và `b@x.com` đều `TESTED`.
  - Test cũ ở dòng ~151 (`{"a@x.com": WRITING, "b@x.com": TODO}`) đổi kỳ vọng thành cả hai `WRITING`.
- [ ] **Step 2:** `cd backend && uv run pytest tests/test_assignment_status.py -q` → FAIL ở hai test mới.
- [ ] **Step 3:** Bỏ điều kiện `case.created_by == tester_email` trong `derive_assignment_status`, sửa docstring.
- [ ] **Step 4:** Chạy cả bộ backend; sửa các test khác chỉ khi chúng khẳng định luật cũ (ví dụ "tester B vẫn TODO khi A viết case"), đổi kỳ vọng theo luật mới và ghi comment lý do.
- [ ] **Step 5:** Đổi nhãn `WRITING` trong `vi.json` thành `"Đang làm"`; chạy `npx vitest run` (sửa test frontend nào khớp chữ "Đang viết").
- [ ] **Step 6: Commit** `fix(backend): trạng thái việc tính mọi case của màn hình` (kèm `vi.json` qua `git add -p`).

### Task 2: Tách quyền sửa và quyền chạy (`can_run`)

**Files:**
- Modify: `backend/app/core/permissions.py` (thêm `Action.RUN_TEST_CASE`)
- Modify: `backend/app/core/services/test_cases.py:214-233,317-333`
- Modify: `backend/app/api/routers/test_cases.py:50-58,208-222` (`TestCaseDetail.can_run`)
- Modify: `backend/app/api/routers/manual_results.py:140-141`
- Modify: `DECISIONS.md`
- Test: `backend/tests/test_permissions.py`, `backend/tests/test_test_case_service.py`, `backend/tests/test_manual_results_api.py`, `backend/tests/test_test_cases_api.py`

**Interfaces:**
- Produces:
  - `Action.RUN_TEST_CASE` với `ALLOWED_ROLES = _LEADS | {Role.TESTER}`; trong `can`, tester với `EDIT_TEST_CASE` **hoặc** `RUN_TEST_CASE` trả `owns_or_assigned` (vẫn một chỗ quyết định).
  - `TestCaseService.can_edit(user, case) -> bool`: tester chỉ khi `case.created_by == normalize_email(user.email)`.
  - `TestCaseService.can_run(user, case) -> bool`: tester khi là người tạo hoặc `_is_assigned(user, case.screen_id)`; lead/admin là thành viên luôn được.
  - `TestCaseDetail.can_run: bool` (= `not project.archived and service.can_run(user, case)`).
  - `mark_tested` kiểm tra `can_run` (lỗi `TestCasePermissionError("Bạn không có quyền chạy test case này")`).

- [ ] **Step 1: Viết test đỏ:**
  - `test_permissions.py::test_tester_run_needs_owns_or_assigned`: `can(tester, Action.RUN_TEST_CASE, is_member=True, owns_or_assigned=False) is False`, `True` khi `owns_or_assigned=True`; viewer luôn `False`.
  - `test_test_case_service.py::test_assigned_tester_can_run_but_not_edit_others_case`: case do `a@x.com` tạo trên màn hình giao cho cả a và b → `can_edit(b) is False`, `can_run(b) is True`, `can_edit(a) is True`; `update_content` bởi b ném `TestCasePermissionError`.
  - `test_test_case_service.py::test_mark_tested_by_assigned_runner`: b gọi `mark_tested` case Manual DRAFT của a → status `TESTED`, audit cuối là `MANUAL_TEST` actor b.
  - `test_manual_results_api.py::test_assigned_tester_submits_result_for_lead_case`: lead tạo case Manual trên `SC-0001` (giao cho an), an POST manual-results PASS → 201, `case.status == "TESTED"`.
  - `test_manual_results_api.py::test_unassigned_tester_cannot_submit`: binh (không được giao) → 403.
  - `test_test_cases_api.py::test_detail_exposes_can_run`: an xem case của lead → `can_edit is False`, `can_run is True`; dự án lưu trữ → `can_run is False`.
- [ ] **Step 2:** Chạy các test trên → FAIL.
- [ ] **Step 3:** Cài đặt theo Interfaces. `manual_results.py` dùng `service.can_run`, câu 403 đổi thành `"Bạn không có quyền chạy test case này"`. Giữ `can_archive` dựa trên `can_edit`.
- [ ] **Step 4:** Chạy cả bộ backend; test cũ khẳng định "tester được giao sửa được case người khác" đổi kỳ vọng sang 403 và ghi comment trỏ về spec mục 4.
- [ ] **Step 5:** Thêm mục vào `DECISIONS.md` (ngày 2026-11-19): "Khoá theo người tạo: tester chỉ sửa case mình tạo; được giao màn hình thì chỉ chạy. Trước đây được giao màn hình là sửa được."
- [ ] **Step 6:** `cd frontend && npm run gen:api` để `schema.d.ts` có `can_run`.
- [ ] **Step 7: Commit** `feat(backend): tách quyền sửa và quyền chạy test case`.

### Task 3: FAIL phải có bằng chứng; trang case dùng `can_run`

**Files:**
- Modify: `backend/app/api/routers/manual_results.py:80-89` (`_check_steps` hoặc hàm mới `_check_fail_evidence`)
- Modify: `frontend/components/test-cases/manual-run-panel.tsx:109-118,357-362`
- Modify: `frontend/app/(app)/projects/[projectId]/test-cases/[caseId]/page.tsx:54-58,136-141`
- Modify: `frontend/messages/vi.json` (`manualRun.failNeedsEvidence`, `testCases.detail.runOnlyHint`)
- Test: `backend/tests/test_manual_results_api.py`, `frontend/components/test-cases/manual-run-panel.test.tsx`, `frontend/app/(app)/projects/[projectId]/test-cases/[caseId]/page.test.tsx`

**Interfaces:**
- Consumes: `TestCaseDetail.can_run` (Task 2), `_all_media(body)` có sẵn.

- [ ] **Step 1: Test backend đỏ:**
  - `test_fail_without_evidence_is_rejected`: FAIL có reason + failed_step, không ảnh/video → 422, `detail == "Kết quả Fail cần ít nhất một ảnh hoặc video bằng chứng"`.
  - `test_fail_with_step_screenshot_only_is_accepted`: FAIL chỉ có `screenshot` ở một `step_results` → 201.
  - `test_blocked_without_evidence_is_accepted` → 201.
  - Sửa các test FAIL cũ trong file này cho có bằng chứng (dùng helper ảnh đã có trong file).
- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Thêm kiểm tra `body.status == "FAIL" and not _all_media(body)` → `_unprocessable(...)`. Không đụng `agent.py`. **Step 4:** Chạy cả bộ backend → PASS.
- [ ] **Step 5: Test frontend đỏ:**
  - `manual-run-panel.test.tsx` "FAIL chưa có bằng chứng thì nút Gửi mờ và hiện nhắc": chọn Fail ở một bước, nhập lý do + môi trường → nút `Gửi` disabled, thấy chữ `failNeedsEvidence`; thêm một ảnh (mock MediaPicker như test hiện có) → enabled.
  - `[caseId]/page.test.tsx` "người chỉ chạy được thấy khung chạy và dòng nhắc": `can_edit: false, can_run: true`, Manual DRAFT → có `ManualRunPanel`, có `"Case do người khác viết, cần sửa hãy báo người viết hoặc QA Lead"`, không có form sửa.
- [ ] **Step 6:** Cài đặt: `failOk` thêm điều kiện có ít nhất một media (gồm `evidence` và ảnh từng bước — dùng đúng state đang có trong panel); trang case: `canRun` dùng `testCase.can_run`; khi `can_run && !can_edit` hiện `detail.runOnlyHint` thay cho `readOnlyHint`. Chuỗi mới: `"failNeedsEvidence": "Kết quả Fail cần ít nhất một ảnh hoặc video bằng chứng."`.
- [ ] **Step 7:** Chạy `npx vitest run && npx tsc --noEmit && npx eslint .` → PASS.
- [ ] **Step 8:** Thêm vào `DECISIONS.md`: "Kết quả test tay FAIL phải có ít nhất một ảnh hoặc video (kể cả ảnh từng bước); kết quả của agent không đổi luật."
- [ ] **Step 9: Commit** `feat: kết quả Fail cần bằng chứng, người chạy thấy khung chạy test`.
- [ ] **Step 10:** Ghi tiến độ Đợt 1 vào plan + `HANDOFF.md`, commit `docs: tiến độ nhập test case đợt 1`, dừng cho /compact.

---

## Đợt 2 — Đọc file, ghi hàng loạt, API

> **Tiến độ: XONG (2026-11-19)** — Task 4–7, commit `bfd4b2c`…`c78d01c`; mỗi task đã qua kiểm tra (Task 4 và 6 có 1 vòng sửa). Backend 798 test. Còn Đợt 3.

### Task 4: Bộ đọc file mẫu (hàm thuần)

**Files:**
- Create: `backend/app/core/services/case_import.py`
- Create: `backend/tests/test_case_import_parse.py`
- Modify: `backend/pyproject.toml`, `backend/uv.lock` (qua `uv add openpyxl`)

**Interfaces:**
- Produces (trong `case_import.py`):
  ```python
  SHEET_NAME = "Test case"
  MAX_FILE_BYTES = 2 * 1024 * 1024
  MAX_DATA_ROWS = 2000
  MAX_CASES = 300

  @dataclass(frozen=True)
  class ImportColumn:
      header: str          # chữ đúng ở dòng 1, ví dụ "Mã nhóm"
      field: str | None    # tên trường TestCaseContent; None cho "Mã nhóm"/"Màn hình"/bước
      level: Literal["group", "case", "step"]
      required: bool
      choices: tuple[str, ...] = ()   # cho data validation của file mẫu

  COLUMNS: tuple[ImportColumn, ...]   # đúng 16 cột, đúng thứ tự spec mục 1

  class ImportIssue(BaseModel):
      row: int | None
      column: str | None = None
      message: str

  class ParsedCase(BaseModel):
      group: str
      row: int                 # dòng đầu của nhóm
      screen_id: str
      screen_name: str
      title: str
      step_count: int
      content: TestCaseContent  # execution_mode luôn MANUAL, không media

  class ParseResult(BaseModel):
      cases: list[ParsedCase] = []
      errors: list[ImportIssue] = []
      warnings: list[ImportIssue] = []

  def parse_workbook(data: bytes, screens: list[Screen]) -> ParseResult: ...
  ```
  `parse_workbook` chưa xét quyền và trùng tiêu đề (Task 6 làm). Lỗi xếp theo `row` (None đứng đầu).

- [ ] **Step 1:** `cd backend && uv add openpyxl`.
- [ ] **Step 2: Viết test đỏ** (helper `make_xlsx(rows, *, header=HEADERS, sheet="Test case") -> bytes` dựng bằng openpyxl; `HEADERS = [c.header for c in COLUMNS]`; hai màn hình `SC-0001 "Đăng nhập"`, `SC-0002 "Giỏ hàng"`):
  - `test_groups_rows_into_cases_in_order`: nhóm A1 3 dòng + A2 1 dòng → 2 case, A1 `step_count == 3`, bước theo thứ tự, `row == 2`, `screen_id == "SC-0001"`, `content.execution_mode == ExecutionMode.MANUAL`.
  - `test_wrong_header_stops`: đổi cột 4 thành `"Ten"` → `errors == [ImportIssue(row=1, column="Ten", message=...)]`, message bắt đầu `"File không đúng mẫu, hãy tải file mẫu mới"`, `cases == []`.
  - `test_header_ignores_case_spaces_and_extra_columns`: `" mã NHÓM "` và thêm cột thứ 17 → không lỗi.
  - `test_group_must_be_contiguous`: A1, A2, A1 → lỗi ở dòng của A1 thứ hai.
  - `test_case_cell_conflict_in_later_row`: dòng 2 của A1 có Tiêu đề khác → lỗi `column="Tiêu đề"`; dòng sau để trống hoặc giống hệt thì không lỗi.
  - `test_blank_row_skipped_and_missing_group_is_error`.
  - `test_screen_by_name_or_id_and_ambiguous_name`: `"đăng nhập "` khớp; `"SC-0002"` khớp; thêm màn hình thứ ba cũng tên "Đăng nhập" → lỗi `"Có nhiều màn hình tên này, hãy ghi mã màn hình"`; tên lạ → lỗi `column="Màn hình"`.
  - `test_choice_values`: `"high"` → `Severity.HIGH`; `"P4"` → lỗi `column="Ưu tiên"`; Regression `"x"`, `"Yes"`, `True`, `"Có"` → True; trống → False; Nền tảng trống → WEB.
  - `test_numbers_read_as_text`: Mã nhóm số `1` và `2.0` → group `"1"`, `"2"`; Dữ liệu test ô ngày → chuỗi ISO.
  - `test_more_than_50_steps_is_error_in_vietnamese`: 51 dòng cùng nhóm → một lỗi tiếng Việt ở dòng đầu nhóm (không chứa chữ tiếng Anh của Pydantic như `"List should have"`).
  - `test_required_fields`: thiếu Kết quả mong đợi → lỗi `column="Kết quả mong đợi"`, message `"Không được để trống"`.
  - `test_limits`: 2001 dòng dữ liệu → một lỗi `row=None`; 301 nhóm → một lỗi `row=None`.
  - `test_reads_first_sheet_when_name_differs` và `test_ignores_guide_sheet` (workbook có sheet `Hướng dẫn` đứng trước `Test case`).
  - `test_not_an_xlsx`: `b"a,b,c"` → `errors == [ImportIssue(row=None, message="Không đọc được file .xlsx")]`.
  - `test_formula_cells_use_cached_value` (workbook lưu bằng openpyxl không có giá trị cache → kỳ vọng ô công thức không có cache bị coi là trống; ghi rõ trong comment test).
- [ ] **Step 3:** Chạy → FAIL (ImportError).
- [ ] **Step 4:** Cài đặt. Hướng: `load_workbook(BytesIO(data), read_only=True, data_only=True)`; bắt mọi lỗi mở file → lỗi "Không đọc được file .xlsx". Chuyển ô: `None`→`""`, `bool`→`"Có"/"Không"`, `float` nguyên → `str(int(v))`, `datetime/date` → `isoformat()`, còn lại `str(v).strip()`. Dựng `TestCaseContent` bằng `model_validate`; bắt `ValidationError` và dịch theo `error["type"]` bằng một bảng nhỏ (`missing`/`string_too_short` → "Không được để trống", `string_too_long` → "Quá {max_length} ký tự", `too_long` (list) → "Quá 50 bước", mặc định "Giá trị không hợp lệ"); cột lấy từ `loc[0]` ánh xạ ngược sang `header`.
- [ ] **Step 5:** Chạy → PASS; `uv run mypy app` (thêm `types-openpyxl` dev nếu mypy đòi, hoặc `ignore_missing_imports` cho riêng `openpyxl` trong `pyproject.toml`).
- [ ] **Step 6: Commit** `feat(backend): đọc file Excel test case theo mẫu`.

### Task 5: Ghi hàng loạt (mã, dòng, audit)

**Files:**
- Modify: `backend/app/core/ids.py` (thêm `next_ids`)
- Modify: `backend/app/core/repositories/test_cases.py` (thêm `create_many`)
- Modify: `backend/app/core/repositories/audit_log.py` (thêm `record_many`)
- Test: `backend/tests/test_ids.py`, `backend/tests/test_test_case_repository.py`, `backend/tests/test_audit_log_repository.py`

**Interfaces:**
- Produces:
  - `IdGenerator.next_ids(entity: str, prefix: str, count: int, *, digits: int = 4) -> list[str]` — cùng khoá Redis với `next_id`; `count <= 0` trả `[]` không gọi Google.
  - `TestCaseRepository.create_many(items: list[tuple[str, TestCaseContent]], *, actor: str) -> list[TestCase]` — `items` là `(screen_id, content)`; trong `self.lock()`, cấp lô mã `("tc", "TC", digits=6)`, một `append_many`, `invalidate` một lần. Case: `DRAFT`, version 1, `created_by = updated_by = actor`.
  - `AuditLogRepository.record_many(entries: list[AuditRecord]) -> None` với `AuditRecord` là `TypedDict`/dataclass `{actor, action, entity, entity_id, diff}`; một `append_many`.

- [ ] **Step 1: Test đỏ:**
  - `test_ids.py::test_next_ids_continues_counter`: `next_id` → `TC-000001`; `next_ids(..., 3)` → `["TC-000002","TC-000003","TC-000004"]`; `next_id` tiếp → `TC-000005`. `test_next_ids_on_empty_meta` → bắt đầu từ 1.
  - `test_ids.py::test_next_ids_call_count_is_constant`: số phần tử `gateway.calls` tăng khi `count=1` bằng khi `count=100`.
  - `test_test_case_repository.py::test_create_many_appends_once`: 3 case → `list_all()` có 3 case đúng screen/title; số lần `append_rows` vào tab TestCases tăng đúng 1 (đếm trong `gateway.calls`).
  - `test_audit_log_repository.py::test_record_many_single_append`: 2 entry → `list_for` mỗi case thấy entry; một lần append.
- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Cài đặt (`next_id` có thể gọi lại `next_ids(..., 1)[0]`). **Step 4:** Chạy cả bộ backend → PASS.
- [ ] **Step 5: Commit** `feat(backend): cấp mã và ghi test case theo lô`.

### Task 6: `TestCaseService.import_cases` + thông báo

**Files:**
- Modify: `backend/app/core/services/test_cases.py`
- Modify: `backend/app/core/services/case_import.py` (thêm `check_import`)
- Modify: `backend/app/core/services/notify.py` (thêm `cases_imported`)
- Create: `backend/tests/test_case_import_service.py`

**Interfaces:**
- Consumes: `ParseResult`, `ParsedCase`, `ImportIssue` (Task 4); `create_many`, `record_many` (Task 5); `can_run`/`_is_assigned` (Task 2).
- Produces:
  - `check_import(result: ParseResult, *, existing: list[TestCase], allowed_screen_ids: set[str] | None) -> ParseResult` (trong `case_import.py`, hàm thuần): thêm lỗi `"Bạn chưa được giao màn hình này"` (`column="Màn hình"`, ở dòng đầu nhóm) khi `allowed_screen_ids` không chứa màn hình (None = mọi màn hình); thêm cảnh báo `"Màn hình {tên} đã có case cùng tiêu đề"` khi tiêu đề (strip + casefold) trùng case cùng màn hình không ở `ARCHIVED`/`DEPRECATED`.
  - `TestCaseService.preview_import(user: User, data: bytes) -> ParseResult` — đọc màn hình, assignment, case hiện có rồi gọi `parse_workbook` + `check_import`. Người không có quyền `EDIT_TEST_CASE` → `TestCasePermissionError`.
  - `TestCaseService.import_cases(user: User, data: bytes) -> ImportOutcome` với `ImportOutcome(created: list[TestCase], errors: list[ImportIssue])`; còn lỗi thì `created=[]`, không ghi gì.
  - `class ImportWriteError(Exception)` — lỗi Sheet trước khi ghi xong (router đổi thành 503).
  - `Notifier.cases_imported(*, email: str, project_id: str, count: int, screen_names: list[str]) -> None` — type `"cases_imported"`, title `f"Có {count} case mới cần chạy ở: {', '.join(screen_names)}"`, link `f"/projects/{project_id}/test-cases"`.

- [ ] **Step 1: Test đỏ** (dựng service như `test_test_case_service.py` đang làm; file xlsx bằng helper của Task 4 — chuyển `make_xlsx` sang `tests/xlsx_helpers.py` để dùng chung):
  - `test_lead_imports_all_screens`: 2 nhóm trên 2 màn hình → `created` 2 case, `MANUAL`, `DRAFT`, `created_by == "lead@x.com"`; audit mỗi case action `"IMPORT"`.
  - `test_tester_cannot_import_unassigned_screen`: an được giao SC-0001, file có nhóm SC-0002 → `errors` có `"Bạn chưa được giao màn hình này"`, `list_all()` rỗng.
  - `test_errors_write_nothing`: một nhóm thiếu Tiêu đề → `created == []`, không case, không audit, `gateway.calls` không có append vào TestCases/AuditLog.
  - `test_screen_deleted_between_preview_and_import`: xoá SC-0002 trước khi `import_cases` → lỗi ở dòng nhóm đó, không ghi gì. *(Review Focus 4)*
  - `test_duplicate_title_warns_not_blocks`: đã có case "Đăng nhập đúng" trên SC-0001 → `preview_import` có warning; `import_cases` vẫn tạo.
  - `test_import_call_count_constant`: đo số phần tử `gateway.calls` khi nhập 1 case và khi nhập 100 case (cùng một màn hình, trên hai môi trường mới) → bằng nhau. *(Review Focus 5)*
  - `test_assignment_status_refreshed_once_per_screen`: sau khi lead nhập cho SC-0001 giao an → assignment của an là `WRITING`.
  - `test_lead_import_notifies_assigned_testers_once`: an được giao SC-0001 và SC-0002, lead nhập 3 case trên hai màn hình → an nhận đúng 1 thông báo `"Có 3 case mới cần chạy ở: Đăng nhập, Giỏ hàng"`; tester tự nhập → không thông báo.
  - `test_sheet_error_before_write_raises_import_write_error`: `gateway.denied` cho spreadsheet ngay trước `create_many` (hook `after_next_read`) → `ImportWriteError`, không case.
  - `test_audit_failure_after_write_is_logged_only`: monkeypatch `record_many` ném `SheetAccessDeniedError` → vẫn trả `created`.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt `import_cases`: kiểm quyền (`can(... EDIT_TEST_CASE, owns_or_assigned=True)`); `with self._assignments.lock(), self._test_cases.lock():` đọc màn hình + assignments + cases (thẳng Sheet), `parse_workbook` + `check_import` (`allowed_screen_ids=None` cho lead/admin, tập màn hình được giao cho tester); có lỗi → trả; không lỗi → `create_many` (bọc `SheetAccessDeniedError`/`MissingColumnsError`/`HttpError` thành `ImportWriteError`). Sau khi nhả khoá: `record_many` (diff như CREATE qua `_strip_media`, lỗi chỉ log), `_refresh_status` mỗi màn hình một lần, thông báo nếu người nhập là QA Lead/Admin (gom theo tester được giao các màn hình đó, bỏ chính người nhập). `LockTimeout` để nổi lên cho router.
- [ ] **Step 4:** Chạy cả bộ backend → PASS.
- [ ] **Step 5: Commit** `feat(backend): nhập test case hàng loạt từ file`.

### Task 7: API template / preview / import

**Files:**
- Create: `backend/app/api/routers/case_import.py`
- Modify: `backend/app/main.py` (hoặc nơi `include_router`; tìm bằng `grep -rn include_router backend/app`)
- Modify: `backend/app/core/services/case_import.py` (thêm `build_template() -> bytes`)
- Create: `backend/tests/test_case_import_api.py`
- Modify: `frontend/lib/api/openapi.json`, `frontend/lib/api/schema.d.ts` (qua `npm run gen:api`)

**Interfaces:**
- Consumes: `preview_import`, `import_cases`, `ImportWriteError` (Task 6); `service_for` từ `routers/test_cases.py`; `load_project(..., Action.EDIT_TEST_CASE)`.
- Produces (router prefix `/api/projects/{project_id}/test-cases/import`, đăng ký **trước** router test_cases để `/import` không bị `/{case_id}` bắt):
  - `GET /template` → `Response` media type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `Content-Disposition: attachment; filename="mau-test-case.xlsx"`.
  - `POST /preview` (`file: UploadFile`) → `ParseResult` (200).
  - `POST ""` (`file: UploadFile`) → 201 `ImportCreated {created: list[str]}`; còn lỗi → 422 `{"detail": "File còn lỗi", "errors": [...]}`; `ImportWriteError` → 503 câu spec; `LockTimeout` → 409 câu spec.
  - Kiểm tra file ở router: đuôi không phải `.xlsx` → `ParseResult(errors=[ImportIssue(row=None, message="Chỉ nhận file .xlsx")])` (preview) / 422 (import); quá `MAX_FILE_BYTES` → lỗi `"File quá 2 MB"`.
  - `build_template()`: sheet `Test case` (tiêu đề in đậm, `freeze_panes="A2"`, data validation danh sách cho cột có `choices`, Regression `"Có,Không"`), 1 case ví dụ 3 bước, sheet `Hướng dẫn` liệt kê luật spec mục 1 bằng tiếng Việt.

- [ ] **Step 1: Test đỏ:**
  - `test_template_roundtrips`: tải template → `parse_workbook(bytes, screens)` với màn hình tên đúng như ví dụ trong template → không lỗi, 1 case 3 bước. (Ví dụ dùng màn hình `"Đăng nhập"`; test tạo màn hình tên đó.)
  - `test_template_has_validation_and_guide`: mở bằng openpyxl → có sheet `Hướng dẫn`, `ws.data_validations.dataValidation` không rỗng, `ws.freeze_panes == "A2"`.
  - `test_preview_writes_nothing`: POST preview → 200, `cases` 1 phần tử, tab TestCases không đổi.
  - `test_import_creates_and_returns_ids`: 201, `created == ["TC-000001"]`, GET case đó có `can_edit` true với lead.
  - `test_import_with_errors_is_422_with_list`.
  - `test_wrong_extension_and_too_big`: `.csv` → lỗi `"Chỉ nhận file .xlsx"`; 2 MB + 1 byte → `"File quá 2 MB"`.
  - `test_garbage_xlsx_is_not_500`: bytes rác đuôi .xlsx → preview 200 có lỗi `"Không đọc được file .xlsx"`. *(Review Focus 2)*
  - `test_viewer_forbidden_and_archived_project_409`.
  - `test_lock_busy_is_409` (giữ khoá `lock:{pid}:test-cases` bằng redis trước khi gọi) → 409 `"Có người đang tạo case, hãy thử lại"`.
- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Cài đặt. **Step 4:** Chạy cả bộ backend + mypy + ruff → PASS.
- [ ] **Step 5:** `cd frontend && npm run gen:api`; `npx tsc --noEmit` → PASS.
- [ ] **Step 6: Commit** `feat(backend): API tải mẫu, xem trước và nhập file test case`.
- [ ] **Step 7:** Ghi tiến độ Đợt 2 vào plan + `HANDOFF.md`, commit docs, dừng cho /compact.

---

## Đợt 3 — Giao diện và tài liệu

### Task 8: Hook gọi API nhập file

**Files:**
- Create: `frontend/lib/use-case-import.ts`
- Create: `frontend/lib/use-case-import.test.tsx`

**Interfaces:**
- Consumes: `ParseResult`, `ImportCreated` trong `schema.d.ts` (Task 7); `ApiError`, `errorMessage` từ `lib/api/client`.
- Produces:
  - `templateUrl(projectId: string): string` → `/api/projects/${encodeURIComponent(projectId)}/test-cases/import/template`.
  - `usePreviewImport(projectId)` → `useMutation<ParseResult, ApiError, File>`.
  - `useImportCases(projectId)` → `useMutation<ImportCreated, ApiError, File>`; thành công thì `invalidateQueries({ queryKey: ["projects", projectId] })`. Lỗi 422 giữ `body.errors` trong `ApiError.body`.
  - Gửi bằng `fetch` + `FormData` (trường `file`), `credentials: "same-origin"`; không dùng XHR (không cần tiến độ).

- [ ] **Step 1: Test đỏ** (mock `fetch`): preview gửi đúng URL và FormData có `file`; import 201 → làm mới cache dự án; 503 → `ApiError.message` là câu backend; 422 → `ApiError.body.errors` có độ dài đúng.
- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Cài đặt. **Step 4:** `npx vitest run lib/use-case-import.test.tsx` → PASS.
- [ ] **Step 5: Commit** `feat(frontend): hook xem trước và nhập file test case`.

### Task 9: Hộp thoại "Nhập từ Excel" trên danh sách case

**Files:**
- Create: `frontend/components/test-cases/import-dialog.tsx`
- Create: `frontend/components/test-cases/import-dialog.test.tsx`
- Modify: `frontend/app/(app)/projects/[projectId]/test-cases/page.tsx:86-160`
- Modify: `frontend/app/(app)/projects/[projectId]/test-cases/page.test.tsx`
- Modify: `frontend/messages/vi.json` (nhóm `testCases.import.*`)

**Interfaces:**
- Consumes: Task 8; `Dialog` từ `components/ui/dialog`; `selectableScreens` từ `lib/test-cases/selectable-screens`.
- Produces: `<ImportDialog projectId={string} open={boolean} onOpenChange={(open: boolean) => void} />`.

- [ ] **Step 1: Test đỏ** (`import-dialog.test.tsx`, mock hook Task 8):
  - Chọn file → gọi preview; hiện `"Xem trước: 12 case · 41 bước · 3 màn hình"` (chuỗi có tham số), bảng có cột Mã nhóm / Màn hình / Tiêu đề / Số bước.
  - Có `errors` → danh sách `"Dòng 7 · Kết quả mong đợi: Không được để trống"` xếp theo dòng, nút `"Nhập 12 case"` disabled; lỗi `row=null` hiện không có tiền tố "Dòng".
  - Chỉ có `warnings` → nút enabled, cảnh báo hiển thị.
  - Bấm Nhập → gọi import với cùng `File`; thành công → `toast.success("Đã nhập 12 case")`, `onOpenChange(false)`.
  - Lỗi 409/503 → hiện câu backend, hộp thoại vẫn mở.
  - Link "Tải file mẫu" có `href === templateUrl(projectId)`.
- [ ] **Step 2: Test đỏ** (`page.test.tsx`): QA Lead thấy nút `"Nhập từ Excel"`; tester không có màn hình được giao thì không thấy; dự án lưu trữ thì không thấy.
- [ ] **Step 3:** Chạy → FAIL.
- [ ] **Step 4:** Cài đặt. Nút hiện khi `canCreate && selectableScreens(screens, assignments, me).length > 0`. Bảng xem trước nằm trong vùng `max-h-[50vh] overflow-auto` để không cuộn cả trang ở 1366×768. `<input type="file" accept=".xlsx">`; chọn lại file thì xem trước lại. Mọi chuỗi ở `vi.json`.
- [ ] **Step 5:** `npx vitest run && npx tsc --noEmit && npx eslint .` → PASS.
- [ ] **Step 6:** Chạy app (skill `run`) với dữ liệu thật hoặc giả: tải mẫu, nhập file mẫu, thấy case mới; chụp màn hình hộp thoại ở 1366×768.
- [ ] **Step 7: Commit** `feat(frontend): hộp thoại nhập test case từ Excel`.

### Task 10: Tài liệu

**Files:**
- Create: `docs/huong-dan-nhap-test-case.md`
- Modify: `HANDOFF.md`, plan này (đánh dấu xong)

- [ ] **Step 1:** Viết hướng dẫn cho QA/tester (tiếng Việt đơn giản): tải mẫu ở đâu, ý nghĩa 16 cột, luật gom nhóm, ví dụ, lỗi hay gặp và cách sửa, ai nhập được màn hình nào, case nhập vào thì tester chỉ chạy, FAIL cần ảnh/video.
- [ ] **Step 2:** Cập nhật `HANDOFF.md` (tính năng xong, thay đổi hành vi khoá case, luật trạng thái việc mới).
- [ ] **Step 3:** Chạy lại cả hai bộ test + mypy + ruff + tsc + eslint, dán kết quả vào báo cáo.
- [ ] **Step 4: Commit** `docs: hướng dẫn nhập test case từ Excel`.

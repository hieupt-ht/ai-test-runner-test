# Test tay (Manual) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi test case có cách chạy `MANUAL` (mặc định) hoặc `AUTOMATION`; tester tự chạy case Manual, gửi kết quả từng bước kèm bằng chứng, và kết quả đi chung đường `Runs`/`Results`/issue GitHub với agent.

**Architecture:** Thêm trường nội dung `execution_mode` (cột cuối tab `TestCases`). Endpoint mới `POST .../test-cases/{case_id}/manual-results` tạo một Run `COMPLETED` + một `Result`, đổi case sang `TESTED`, rồi dùng chung với agent phần thông báo và đồng bộ issue (tách ra `app/api/result_recording.py`). Frontend thêm nút chọn cách chạy ở form, khung "Chạy test tay" ở trang case, nhãn Pass/Fail gần nhất.

**Tech Stack:** FastAPI + pydantic, Google Sheets (`SheetTable`), Redis lock, pytest/mypy/ruff (uv); Next.js 16, TanStack Query, next-intl, vitest.

**Spec:** `docs/superpowers/specs/2026-11-18-manual-test-run-design.md`

**Chia đợt:** Đợt 1 = Task 1–4 (backend). Đợt 2 = Task 5–7 (frontend). Xong mỗi đợt: ghi tiến độ vào plan + `HANDOFF.md`, dừng cho `/compact`.

## Tiến độ

- **Đợt 1 (backend, Task 1–4) xong** — commit `8f5e010`, `f8ac87f`, `ecafe38`, `b7948af`, `1a21868`. Backend **727 test** qua, mypy và ruff sạch.
- Ruling (đã quyết khi làm):
  1. Test cũ viết cho case do agent chạy nên fixture đặt `execution_mode: AUTOMATION` (`BODY` ở `test_test_cases_api`, `content()` ở `test_test_case_service`, `make_case` ở `test_issue_format`); assertion không đổi. Nếu sai: test cũ nhìn như đang kiểm Manual.
  2. Test "mặc định Manual qua API" nằm ở `test_test_cases_api.py` (fixture dùng chung ở đó), không ở `test_execution_mode.py`.
  3. `ManualStepResult` dùng lại `StepResult` (cùng trường). `AgentEvidence` vẫn ở `agent.py`, router test tay import từ đó.
  4. Hai test cũ "tester không được ký/tải vào thư mục evidence" đổi thành "được phép" (đúng yêu cầu spec); `purpose` lạ vẫn 422.
  5. Ảnh Drive không kiểm thư mục (ID file không có đường dẫn); chỉ Cloudinary kiểm tiền tố `ai-test-runner/{pid}/evidence/`.
  6. Nhãn `mode: manual` đặt cuối danh sách nhãn để `labels[1]` vẫn là nhãn case.
- **Đợt 2 (frontend, Task 5–7): chưa làm.**

## Global Constraints

- TDD: viết test, xem đỏ, rồi mới code. Comment tiếng Việt. Conventional Commits: type tiếng Anh, nội dung tiếng Việt có dấu, message bằng heredoc Git Bash.
- Cột Sheet mới luôn nối vào **cuối** `TEST_CASE_COLUMNS`.
- Case mới (API và form) mặc định `MANUAL`; **ô trống ở Sheet cũ đọc thành `AUTOMATION`**.
- Nhãn tiếng Việt của trường: `"execution_mode": "Cách chạy"`.
- Next.js 16: `useParams/useSearchParams` trong `<Suspense>`; sinh lại API bằng `npm run gen:api`.
- Không push/PR khi chưa được đồng ý. Không in `.env`, `worker-projects.json`. Không chạy `ruff format` cả thư mục.
- Cây làm việc có sửa dở của chủ dự án (`case-form*`, `media-picker*`, `vi.json`, vài test backend…): chỉ stage phần của mình (dựng bản chỉ-có-phần-mình rồi `git update-index --cacheinfo`, kiểm bằng `git diff --cached`).
- Lệnh kiểm tra: backend `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check app tests`; frontend `cd frontend && npm run test && npm run typecheck && npm run lint`.

## Review Focus

1. Tester gửi `step_results` thiếu bước, thừa bước hoặc trùng `step_no` → 422, **không** tạo Run nào (Task 3: `test_manual_result_step_mismatch_is_422_without_run`).
2. Bằng chứng Cloudinary nằm ở thư mục `guide` hoặc thư mục `evidence` của dự án khác → 422, không tạo Run (Task 3: `test_manual_result_rejects_non_evidence_folder`).
3. Gửi Fail rồi gửi lại Pass khi case đang `TESTED` → case vẫn `TESTED`, có 2 Run, issue đóng và gỡ nhãn bug (Task 3: `test_manual_fail_then_pass_closes_issue`).
4. Gửi `BLOCKED` khi case `DRAFT` → có Result, case vẫn `DRAFT`, không tạo issue (Task 3: `test_manual_blocked_keeps_draft_and_no_issue`).
5. Tester bấm "Không đạt" ở bước 2 rồi đổi lại "Đạt" → ô `failed_step` không còn kẹt ở 2, gợi ý quay về bước Không đạt đầu tiên còn lại (hoặc trống) (Task 6: `ManualRunPanel` test "đổi lại Đạt thì bỏ gợi ý bước lỗi").

---

## ĐỢT 1 — Backend

### Task 1: Trường `execution_mode` (model, cột Sheet, repository)

**Files:**
- Modify: `backend/app/core/models/test_case.py` (thêm `ExecutionMode`, trường, nhãn)
- Modify: `backend/app/core/sheets/schema.py:55-79` (cột `execution_mode` cuối danh sách)
- Modify: `backend/app/core/repositories/test_cases.py` (`_to_record`, `_from_record`)
- Modify (fixture): `backend/tests/test_test_cases_api.py` (`BODY`), các content factory trong `tests/test_test_case_service.py`, `test_test_case_repository.py`, `test_assignment_status.py`, `test_assignments_api.py`, `test_overview_api.py`, `test_results_api.py`, `test_screens_api.py`, `test_sheet_list_cache.py` — chỉ nơi test cần case Automation
- Test: `backend/tests/test_execution_mode.py` (mới)

**Interfaces:**
- Produces: `class ExecutionMode(StrEnum): MANUAL = "MANUAL"; AUTOMATION = "AUTOMATION"`; `TestCaseContent.execution_mode: ExecutionMode = ExecutionMode.MANUAL`; `CHANGED_FIELD_LABELS["execution_mode"] == "Cách chạy"`.

- [x] **Step 1: Viết test đỏ** trong `tests/test_execution_mode.py`:
  - `test_new_content_defaults_to_manual`: `TestCaseContent(title=..., steps=[...], expected_result=..., severity=..., priority=...)` → `.execution_mode == ExecutionMode.MANUAL`.
  - `test_execution_mode_round_trips_through_sheet`: tạo case `AUTOMATION` qua repository, đọc lại → `AUTOMATION`; ô Sheet cột `execution_mode` là `"AUTOMATION"`.
  - `test_blank_cell_reads_as_automation`: ghi dòng rồi xoá trắng ô `execution_mode` trong `gateway.data` → `get()` trả `AUTOMATION`.
  - `test_api_create_defaults_to_manual`: POST case không có `execution_mode` → 201, `json()["execution_mode"] == "MANUAL"`.
  - `test_execution_mode_has_vietnamese_label`: `CHANGED_FIELD_LABELS["execution_mode"] == "Cách chạy"`.
- [x] **Step 2: Chạy** `cd backend && uv run pytest tests/test_execution_mode.py -q` — Expected: FAIL (ImportError `ExecutionMode`).
- [x] **Step 3: Code** model + cột + repository. `_from_record`: `ExecutionMode(record["execution_mode"].strip().upper() or ExecutionMode.AUTOMATION)`.
- [x] **Step 4: Chạy lại** test mới — Expected: PASS.
- [x] **Step 5: Chạy cả bộ** `uv run pytest -q` — Expected: một số test cũ đỏ vì case mới thành Manual (gửi duyệt sẽ bị chặn ở Task 2, nhưng lúc này chủ yếu do so sánh dict/cột). Sửa **fixture** cho `execution_mode: "AUTOMATION"` (ở `BODY` và các factory), **không** sửa assertion. Ghi Ruling vào ledger: "fixture cũ là case viết cho agent nên đặt AUTOMATION". Chạy lại — Expected: PASS hết.
- [x] **Step 6: Commit** `feat(backend): thêm trường cách chạy (Manual/Automation) cho test case`.

### Task 2: Luật trạng thái case Manual và trạng thái việc

**Files:**
- Modify: `backend/app/core/services/test_cases.py` (`_transition_case`, `update_content`, thêm `mark_tested`)
- Modify: `backend/app/core/assignment_status.py:9-37`
- Test: `backend/tests/test_manual_case_rules.py` (mới)

**Interfaces:**
- Consumes: `ExecutionMode` (Task 1).
- Produces: `TestCaseService.mark_tested(user: User, case_id: str, *, version: int) -> TestCase` — đổi `DRAFT` → `TESTED` (đang `TESTED` thì trả nguyên case, không ghi), AuditLog action `"MANUAL_TEST"`, diff `{"status": ["DRAFT", "TESTED"]}`; case không phải Manual hoặc trạng thái khác `DRAFT`/`TESTED` → `InvalidTransitionError`.
- Produces: hằng `MANUAL_NO_REVIEW = "Case test tay không cần gửi duyệt"`.

- [x] **Step 1: Viết test đỏ** (dùng service với repo giả như `test_test_case_service.py`):
  - `test_manual_case_cannot_be_submitted`: SUBMIT case Manual → `InvalidTransitionError`, `str(error) == MANUAL_NO_REVIEW`.
  - `test_mark_tested_moves_draft_to_tested_with_audit`: → `status == TESTED`, AuditLog cuối có action `MANUAL_TEST`.
  - `test_mark_tested_when_already_tested_keeps_version`.
  - `test_mark_tested_rejects_automation_case`.
  - `test_editing_tested_manual_case_returns_to_draft`: đổi `title` → `DRAFT`, diff có `status`.
  - `test_switching_mode_returns_to_draft`: Automation `APPROVED` → đổi sang Manual → `DRAFT`; Manual `TESTED` → đổi sang Automation → `DRAFT`.
  - `test_manual_edit_never_requests_rerun`: dự án tắt duyệt, case Manual `TESTED` có kết quả, sửa `steps` → `issue_sync.note_case_edited` không được gọi.
  - `test_deprecate_allowed_from_tested_for_manual` và `test_deprecate_from_tested_still_rejected_for_automation`.
  - Trong `tests/test_assignment_status.py`: `test_all_manual_tested_is_tested`, `test_mixed_manual_tested_and_automation_approved_is_approved`, `test_manual_draft_is_writing`.
- [x] **Step 2: Chạy** `uv run pytest tests/test_manual_case_rules.py tests/test_assignment_status.py -q` — Expected: FAIL.
- [x] **Step 3: Code.** `_transition_case`: SUBMIT với case Manual → `InvalidTransitionError(MANUAL_NO_REVIEW)` (trước kiểm tra `allowed_from`); DEPRECATE cho phép thêm `TESTED` khi case Manual. `update_content`: về `DRAFT` khi (a) `execution_mode` đổi, hoặc (b) case cũ Manual và đang `TESTED`, cùng với luật `IN_REVIEW`/`APPROVED` cũ; `keep_status` chỉ áp dụng cho case Automation. `derive_assignment_status`: sau nhánh `IN_REVIEW`, nếu mọi case trong `mine` là Manual `TESTED` → `TESTED`.
- [x] **Step 4: Chạy lại** — Expected: PASS; rồi `uv run pytest -q` — Expected: PASS.
- [x] **Step 5: Commit** `feat(backend): luật trạng thái cho case test tay`.

### Task 3: API gửi kết quả tay + issue cho case Manual

**Files:**
- Create: `backend/app/api/result_recording.py` (phần dùng chung với agent)
- Create: `backend/app/api/routers/manual_results.py`; đăng ký router ở nơi đăng ký các router khác (`app/main.py` hoặc tương đương)
- Modify: `backend/app/api/routers/agent.py` (dùng hàm chung, hành vi giữ nguyên)
- Modify: `backend/app/api/routers/media.py` (`purpose: Literal["guide", "evidence"]` ở `/sign` và `/upload`)
- Modify: `backend/app/api/routers/test_cases.py` (`TestCaseDetail.last_result`)
- Modify: `backend/app/core/services/issue_sync.py` (tạo issue cho Manual `TESTED`, `APP_LABEL_PREFIXES` thêm `"mode:"`)
- Modify: `backend/app/core/github/issue_format.py` (nhãn `mode: manual`; bỏ khối "Báo cáo cho AI Test Runner" khi case Manual)
- Modify: `backend/app/core/services/result_issue_sync.py` (dòng người chạy)
- Test: `backend/tests/test_manual_results_api.py` (mới), thêm vào `tests/test_issue_sync.py`, `tests/test_issue_format.py`, `tests/test_media_api.py`

**Interfaces:**
- Consumes: `TestCaseService.mark_tested` (Task 2), `ExecutionMode` (Task 1).
- Produces (`app/api/result_recording.py`):
  - `notify_results_recorded(services: Services, project: Project, run: Run, *, failed_case_creators: Iterable[str]) -> None` — người nhận: Admin + QA Lead thành viên (đang active) + `failed_case_creators`; lỗi chỉ log.
  - `sync_issues_for_results(services: Services, project: Project, run: Run, results: list[Result], cases: dict[str, TestCase], *, duration: float = 0, runner_name: str | None = None) -> None` — gọi `sync_result_issue` từng kết quả, lỗi từng case chỉ log.
- Produces (endpoint): `POST /api/projects/{project_id}/test-cases/{case_id}/manual-results`, body `ManualResultRequest`, trả `ManualResultResponse{run_id: str, case: TestCase}`, status 201.
  - `ManualStepResult`: `step_no: int (ge=1)`, `status: Literal["PASS","FAIL","SKIPPED"]`, `actual: str (max 1000)`, `screenshot: Media | None`.
  - `ManualResultRequest`: `status: Literal["PASS","FAIL","BLOCKED"]`, `step_results: list[ManualStepResult] (max 50)`, `actual_result: str (max 2000)`, `reason: str (max 2000)`, `failed_step: int | None (ge=1)`, `evidence: AgentEvidence` (video + ≤20 ảnh; dùng lại lớp ở `agent.py` hoặc chuyển sang chỗ chung), `environment: str (min 1, max 200, strip)`, `build_version: str (max 50)`, `assignee: str` (rỗng hoặc khớp `^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$`, max 39), `version: int`.
- Produces: `TestCaseDetail.last_result: LastResult | None`, `LastResult{status: ResultStatus, run_id: str, created_at: datetime}` — chỉ tính cho case Manual (đọc `Results` một lần), case Automation luôn `None`.
- Produces: `issue_format.MODE_MANUAL_LABEL = "mode: manual"`.

Thứ tự kiểm tra trong endpoint (mỗi lỗi trả về trước khi ghi bất cứ gì):
1. `load_project(..., Action.EDIT_TEST_CASE, allow_archived=True)`; `project.archived` → 409 "Dự án đã lưu trữ".
2. Case không có → 404; `not service.can_edit(user, case)` → 403.
3. Case không phải Manual → 409 "Case này chạy tự động, không gửi kết quả tay được"; trạng thái khác `DRAFT`/`TESTED` → 409 "Chỉ gửi kết quả khi case đang Nháp hoặc Đã kiểm thử".
4. `body.version != case.version` → 409 "Case vừa được sửa, hãy tải lại".
5. 422: `step_results` phải đúng một mục cho mỗi bước `1..len(case.steps)`; FAIL thì `reason.strip()` khác rỗng và `failed_step` trong `1..len(case.steps)` — câu báo tiếng Việt cụ thể.
6. 422: `ensure_own_media(...)`; với ảnh/video Cloudinary, `public_id` phải bắt đầu bằng `f"ai-test-runner/{project.id}/evidence/"`.
7. `scope.runs.create(triggered_by=user.email, scope=RunScope(case_ids=[case.id]), branch=project.branch, total=1, build_version=...)`; `RunInProgressError`/`LockTimeout` → 409 "Đang có một lần ghi kết quả khác, hãy thử lại".
8. `scope.results.append_batch([result])` (`executed_by=user.email`, `case_version=body.version`, `dev_owner=body.assignee or dev phụ trách màn hình`); lỗi → Run `FAILED`, 503 (như agent). Thành công → Run `COMPLETED`, `passed`/`failed`.
9. PASS/FAIL → `service.mark_tested(...)` (BLOCKED bỏ qua). Lỗi ở đây chỉ log.
10. `notify_results_recorded` (FAIL thêm người tạo case); đồng bộ issue: một hàm gộp `IssueSyncer.sync_case(project, case_mới)` rồi `sync_issues_for_results(..., runner_name=user.name)`; nếu `services.issue_sync` là `BackgroundIssueSync` thì `submit` vào luồng nền (chạy sau lần sync_case mà `mark_tested` đã xếp hàng), không thì chạy ngay. BLOCKED không đụng issue. Rồi `prune_evidence`.

- [x] **Step 1: Viết test đỏ** `tests/test_manual_results_api.py` (fixture `project`/`lead`/`an` như `test_agent_results_api.py`; case tạo qua API mặc định Manual):
  - `test_tester_submits_pass_marks_tested`: 201; case `TESTED`; Run `COMPLETED`, `triggered_by == "an@x.com"`, `scope.case_ids == ["TC-000001"]`; Result `executed_by == "an@x.com"`, `case_version == 1`.
  - `test_manual_fail_requires_reason_and_failed_step` (422 mỗi trường, không có Run).
  - `test_manual_result_step_mismatch_is_422_without_run` (thiếu / thừa / trùng `step_no`).
  - `test_manual_result_rejects_non_evidence_folder` (`ai-test-runner/PRJ-0001/guide/x` và `ai-test-runner/PRJ-0002/evidence/x` → 422, không Run).
  - `test_manual_result_stale_version_is_409`.
  - `test_manual_result_on_automation_case_is_409`; `test_manual_result_on_archived_project_is_409`; `test_other_tester_without_assignment_is_403`.
  - `test_manual_blocked_keeps_draft_and_no_issue`: Result ghi, case `DRAFT`, `github` giả không có issue.
  - `test_first_fail_creates_issue_assigns_and_labels`: issue có nhãn `mode: manual`, `status:TESTED`, `test: fail`, `bug: cần sửa`; assignee = `assignee` gửi lên; comment có "Người chạy" và **không** có email.
  - `test_manual_fail_then_pass_closes_issue`.
  - `test_manual_result_sheet_error_marks_run_failed_503`.
  - `test_manual_fail_notifies_case_creator_and_leads`.
  - `test_case_detail_has_last_result_for_manual_only`.
  - `test_media_sign_accepts_evidence_purpose` (`tests/test_media_api.py`).
  - `tests/test_issue_sync.py`: `test_switching_to_automation_drops_mode_label`; `tests/test_issue_format.py`: `test_manual_issue_has_mode_label_and_no_agent_block`.
- [x] **Step 2: Chạy** `uv run pytest tests/test_manual_results_api.py tests/test_issue_sync.py tests/test_issue_format.py tests/test_media_api.py -q` — Expected: FAIL (404/405 vì chưa có route).
- [x] **Step 3: Tách** `notify_results_recorded` và `sync_issues_for_results` từ `agent.py` sang `app/api/result_recording.py`; chạy `uv run pytest tests/test_agent_results_api.py -q` — Expected: PASS (hành vi agent không đổi).
- [x] **Step 4: Code** endpoint, media purpose, issue sync/format, `last_result`, dòng `**Người chạy:** <tên> (test tay)` (qua `_safe_text`) khi `runner_name` có.
- [x] **Step 5: Chạy lại** các test ở Step 2 — Expected: PASS; rồi bộ kiểm tra backend đầy đủ — Expected: PASS, mypy/ruff sạch.
- [x] **Step 6: Commit** (có thể 2 commit) `refactor(backend): tách phần ghi kết quả dùng chung với agent` và `feat(backend): API gửi kết quả test tay và issue cho case Manual`.

### Task 4: Agent và regression bỏ qua case Manual + tài liệu Codex

**Files:**
- Modify: `backend/app/api/routers/agent.py:172-204`
- Modify: `backend/app/api/routers/regression.py:85-92`
- Modify: `docs/codex-agent.md` (prompt các máy: luôn bỏ qua issue có nhãn `mode: manual`)
- Test: `backend/tests/test_agent_results_api.py`, `backend/tests/test_regression_api.py`

**Interfaces:**
- Consumes: `ExecutionMode` (Task 1).

- [x] **Step 1: Viết test đỏ:** `test_agent_ignores_manual_case` (case Manual → `ignored == [{"test_case_id": ..., "reason": "Case test tay"}]`, `written == 0`, case không đổi trạng thái); `test_regression_run_skips_manual_cases` (dữ liệu Sheet có một case `regression=True`, `APPROVED`, `MANUAL` ghi thẳng vào `gateway.data` cùng một case Automation → `scope.case_ids` chỉ có case Automation).
- [x] **Step 2: Chạy** hai file test — Expected: FAIL.
- [x] **Step 3: Code:** agent kiểm tra case Manual **trước** kiểm tra "chưa duyệt" (đọc mọi case, không chỉ `APPROVED`); regression lọc thêm `execution_mode == AUTOMATION`. Sửa `docs/codex-agent.md`.
- [x] **Step 4: Chạy** bộ kiểm tra backend đầy đủ — Expected: PASS.
- [x] **Step 5: Commit** `feat(backend): agent và regression bỏ qua case test tay`. Ghi tiến độ đợt 1 vào plan + `HANDOFF.md` (commit `docs: tiến độ test tay đợt 1`), dừng cho `/compact`.

---

## ĐỢT 2 — Frontend

### Task 5: Chọn cách chạy ở form, cột và bộ lọc ở danh sách

**Files:**
- Regenerate: `frontend/lib/api/openapi.json`, `schema.d.ts` (`npm run gen:api`)
- Modify: `frontend/lib/api/types.ts` (export `ExecutionMode`, `ManualResultRequest`, `LastResult` nếu file đang re-export kiểu)
- Modify: `frontend/lib/test-cases/form-schema.ts`, `components/test-cases/case-form.tsx` (+ test)
- Modify: `frontend/lib/test-cases/actions.ts` (+ test), `lib/test-cases/filter.ts` (+ test), `lib/test-cases/history.ts` (nhãn "Cách chạy")
- Modify: `frontend/app/(app)/projects/[projectId]/test-cases/page.tsx`, `components/test-cases/filters-bar.tsx`
- Modify: `frontend/messages/vi.json`

**Interfaces:**
- Produces: `availableActions(status, canEdit, canReview, executionMode: ExecutionMode)` — Manual không có `"submit"`; mọi chỗ gọi cũ truyền thêm `testCase.execution_mode`.
- Produces: `CaseFilters.executionMode?: ExecutionMode`.

- [ ] **Step 1: Viết test đỏ:** `actions.test.ts` ("case Manual Nháp không có submit"); `filter.test.ts` (lọc theo `executionMode`); `case-form.test.tsx` ("case mới mặc định Manual", "bấm Automation hiện ghi chú *Agent sẽ chạy sau khi case được duyệt* và gửi `execution_mode: AUTOMATION`"); `history.test.ts` (`execution_mode` → "Cách chạy").
- [ ] **Step 2: Chạy** `cd frontend && npm run test` — Expected: FAIL ở các test mới.
- [ ] **Step 3: Code:** hai nút (`aria-pressed`) ở đầu form; cột/nhãn "Cách chạy" + bộ lọc ở danh sách; chuỗi tiếng Việt `testCases.executionMode`, `executionManual` ("Test tay"), `executionAutomation` ("Tự động"), `automationNote`.
- [ ] **Step 4: Chạy** bộ kiểm tra frontend — Expected: PASS.
- [ ] **Step 5: Commit** (chỉ phần của mình ở `case-form*`, `vi.json`) `feat(frontend): chọn cách chạy Manual/Automation cho test case`.

### Task 6: Khung "Chạy test tay"

**Files:**
- Modify: `frontend/lib/media/upload.ts` (+ test), `components/media/media-picker.tsx` (prop `purpose`)
- Create: `frontend/lib/use-manual-result.ts` (+ test)
- Create: `frontend/components/test-cases/manual-run-panel.tsx` (+ `.test.tsx`)
- Modify: `frontend/messages/vi.json`

**Interfaces:**
- Produces: `uploadMedia(file, { ..., purpose?: "guide" | "evidence" })` (mặc định `"guide"`, gửi đúng `purpose` cho cả `/sign` và `/upload`); `MediaPicker` prop `purpose?: "guide" | "evidence"`.
- Produces: `useSubmitManualResult(projectId: string, caseId: string)` → `mutateAsync(body: ManualResultRequest)`; `onSuccess` invalidate `["projects", projectId]` và `["me", "assignments"]`.
- Produces: `<ManualRunPanel projectId storage testCase onDone? />`.

- [ ] **Step 1: Viết test đỏ** `manual-run-panel.test.tsx` (mock hook + `MediaPicker`):
  - "nút Gửi khoá khi chưa chọn kết quả cho mọi bước" và "khi chưa nhập Môi trường".
  - "chọn Không đạt ở bước 2 thì gợi ý Fail và bước lỗi = 2".
  - "đổi lại Đạt thì bỏ gợi ý bước lỗi" (Review Focus 5).
  - "Fail thì bắt buộc mô tả lỗi".
  - "Giao cho mặc định là dev phụ trách màn hình" (prop `defaultAssignee`).
  - "khoá nút Gửi khi MediaPicker báo đang tải".
  - "gửi đúng body (status, step_results, environment, version…)" và "nhớ Môi trường lần trước" (`localStorage` bọc try/catch).
  - `upload.test.ts`: "purpose evidence được gửi lên khi ký Cloudinary và khi tải Drive".
- [ ] **Step 2: Chạy** `npm run test` — Expected: FAIL.
- [ ] **Step 3: Code** theo phác thảo ở mục 5 của spec; chuỗi tiếng Việt `manualRun.*`.
- [ ] **Step 4: Chạy** bộ kiểm tra frontend — Expected: PASS.
- [ ] **Step 5: Commit** (chỉ phần của mình ở `media-picker*`, `vi.json`) `feat(frontend): khung chạy test tay và gửi kết quả`.

### Task 7: Gắn vào trang case + nhãn Pass/Fail gần nhất

**Files:**
- Modify: `frontend/app/(app)/projects/[projectId]/test-cases/[caseId]/page.tsx` (+ test nếu có)
- Modify: `frontend/components/test-cases/status-badge.tsx` (prop `lastResult?`)
- Modify: `frontend/app/(app)/projects/[projectId]/test-cases/page.tsx` (dùng `useResults(projectId)` đã có — một request, map `case_id → status` — cho nhãn Pass/Fail)
- Modify: `frontend/messages/vi.json`

**Interfaces:**
- Consumes: `ManualRunPanel` (Task 6), `TestCaseDetail.last_result` (Task 3), `useResults` (`lib/use-results.ts`).

- [ ] **Step 1: Viết test đỏ:** trang case Manual có quyền → có khung "Chạy test tay", không có nút "Gửi duyệt"; case Automation → không có khung, vẫn có "Gửi duyệt"; dự án lưu trữ / không có quyền → không có khung; case `TESTED` có `last_result` FAIL → nhãn "Đã kiểm thử · Fail" và dòng "Lần chạy gần nhất: Fail · RUN-0001 · <giờ>" có link sang `/projects/{id}/results`; case `DRAFT` không hiện Pass/Fail.
- [ ] **Step 2: Chạy** `npm run test` — Expected: FAIL.
- [ ] **Step 3: Code.**
- [ ] **Step 4: Chạy** bộ kiểm tra frontend **và** backend — Expected: PASS hết.
- [ ] **Step 5: Commit** `feat(frontend): trang case hiện chạy test tay và kết quả gần nhất`. Ghi tiến độ đợt 2 vào plan + `HANDOFF.md`, dừng cho `/compact`. Sau đó: review cả nhánh (reviewer mới, model mạnh nhất, kèm Review Focus ở trên).

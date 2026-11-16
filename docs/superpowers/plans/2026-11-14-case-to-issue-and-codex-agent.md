# Case → GitHub issue và Codex agent đọc issue: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khi một test case được duyệt, backend tạo (hoặc cập nhật) một GitHub issue cho case đó ở repo của dự án; Codex đọc issue qua GitHub MCP, chạy test, rồi ghi kết quả lên issue và vào tab `Results` của Sheet.

**Architecture:** Sheet vẫn là nơi lưu chính; issue là **bản sao một chiều** tìm bằng label `tc:<mã case>` (không thêm cột Sheet). Đồng bộ chạy nền trong một luồng duy nhất (tuần tự để không dồn lượt gọi GitHub), sau khi Sheet đã ghi, và lỗi GitHub không bao giờ làm hỏng việc lưu case. Codex chạy ngoài ứng dụng; việc duy nhất nó cần từ ai-test-runner là một API nhỏ có token để ghi kết quả.

**Tech Stack:** Như hiện có (FastAPI, `httpx`, Redis, Google Sheets, Next.js). Không thêm thư viện.

**Spec:** `docs/superpowers/specs/2026-11-14-case-to-issue-and-codex-agent-design.md` (mục 4 và mục 6 là quyết định đã chốt). Đọc thêm `HANDOFF.md`, `AGENTS.md`, `DECISIONS.md`.

## Global Constraints

- Làm trên nhánh `feature/ai-agent-runner` (từ `develop`). **Không push, không tạo PR khi chưa được chủ dự án đồng ý.**
- Commit theo Conventional Commits: type tiếng Anh, nội dung tiếng Việt có dấu; viết message bằng heredoc Git Bash; kết thúc bằng dòng `Co-Authored-By` mà môi trường yêu cầu. TDD: viết test, xem nó đỏ, rồi mới viết code. Mỗi task kết thúc bằng bộ test đầy đủ xanh: `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check`; frontend: `npx vitest run && npm run typecheck && npm run lint`.
- Giữ quy tắc cũ: chỉ `gateway.py` gọi Google; mọi thao tác Sheet qua repository; lỗi API là `{"detail": "<câu tiếng Việt>"}`; chuỗi giao diện ở `frontend/messages/vi.json`; `mypy --strict`, `ruff` sạch.
- **Issue chỉ tạo khi case `APPROVED`** (quyết định 1). Case đã có issue thì được cập nhật ở mọi lần đổi (sửa, trả lại, ngừng dùng, khôi phục).
- Issue nằm ở **repo của dự án**: `Project.repo_full_name`.
- Đặt tên: label `test-case` (mọi issue case), label `tc:TC-000123`, label `status:APPROVED` (một trong `DRAFT`/`IN_REVIEW`/`APPROVED`/`DEPRECATED`); tiêu đề `[TC-000123] <tiêu đề case>`.
- **Repo công khai** (quyết định 4): thân issue **không chứa `test_data`**, không chứa email của người tạo/sửa (nên không có `created_by`/`updated_by`).
- Case `DEPRECATED` → đóng issue; case khác trạng thái đó mà issue đang đóng → mở lại.
- Mã case (`TC-000123`) đánh số theo từng dự án nên **lặp lại giữa các dự án**: mọi khoá chung (Redis, thư mục, label tìm kiếm) phải kèm mã dự án hoặc repo. (Lỗi nghiêm trọng đã gặp ở M4.)
- Hạn mức: GitHub bị giới hạn lượt gọi, Google Sheets ~60 lượt đọc/phút. Đồng bộ issue chạy **tuần tự trong một luồng nền**, không gọi song song.
- Không in hay commit giá trị trong `.env`. Token của agent (`AGENT_API_TOKEN`) chỉ ở `.env`, không ở Sheet, log hay response.

## Review Focus

1. **GitHub lỗi (hết quota, App chưa cài, mất mạng) khi duyệt case** → case vẫn lưu và trả thành công, không sinh case trùng, có log. Test ở Task 4.
2. **Đồng bộ hai lần cho cùng một case (bấm duyệt lại, "Đồng bộ lại")** → vẫn đúng **một** issue, không trùng. Test ở Task 3.
3. **`test_data` và email không bao giờ có trong thân issue** (repo công khai). Test ở Task 2.
4. **Dự án chưa cấu hình GitHub (`services.github is None`), hoặc repo chưa được cài App** → bỏ qua đồng bộ êm, không làm hỏng việc lưu. Test ở Task 3 và 4.
5. **API ghi kết quả của agent:** không đặt token → tắt hẳn; sai token → 401; token đúng nhưng mã case không thuộc dự án → bỏ qua và báo; một dự án không ghi được vào dự án khác. Test ở Task 6.

---

## File Structure

```
backend/app/
├── core/
│   ├── github/client.py              # + IssueInfo, các hàm issue/label trong GitHubClient và GitHubAppClient
│   ├── github/issue_format.py        # MỚI: render_issue(case) -> IssueContent
│   ├── services/issue_sync.py        # MỚI: IssueSyncer, BackgroundIssueSync
│   ├── services/test_cases.py        # + gọi đồng bộ sau khi ghi Sheet
│   ├── models/run.py, repositories/runs.py, sheets/table.py   # lấy lại từ tag m4-playwright-v1 (Task 6)
├── api/
│   ├── services.py                   # + issue_sync
│   ├── routers/test_cases.py         # + POST /sync-issues
│   └── routers/agent.py              # MỚI: ghi kết quả bằng token (Task 6)
└── settings.py                       # + agent_api_token
backend/tests/{test_github_issues.py,test_issue_format.py,test_issue_sync.py,test_agent_results_api.py}
frontend/components/test-cases/       # nút "Đồng bộ lại issue" (Task 5)
docs/codex-agent.md                   # hướng dẫn cấu hình Codex (Task 7)
```

---

### Task 1: GitHubClient biết làm việc với issue và label

**Files:**
- Modify: `backend/app/core/github/client.py`, `backend/tests/fakes.py` (mở rộng `FakeGitHub`)
- Test: `backend/tests/test_github_issues.py` (theo mẫu `tests/test_github_client.py`: `httpx.MockTransport`)

**Interfaces:**
- Produces trong `client.py`: `IssueInfo(number: int, url: str, state: Literal["open","closed"], title: str, labels: list[str])` (Pydantic) và trong `GitHubClient` (Protocol) cùng `GitHubAppClient`:
  - `find_issue_by_label(repo_full_name: str, label: str) -> IssueInfo | None` (tìm cả issue mở lẫn đóng; nhiều issue cùng label thì lấy số nhỏ nhất)
  - `create_issue(repo_full_name: str, *, title: str, body: str, labels: list[str]) -> IssueInfo`
  - `update_issue(repo_full_name: str, number: int, *, title: str, body: str, labels: list[str], state: Literal["open","closed"]) -> IssueInfo`
  - `ensure_label(repo_full_name: str, name: str) -> None` (tạo nếu chưa có; 422 "already exists" coi như đã có)
- `FakeGitHub` giữ `issues: dict[str, list[IssueInfo + body]]` theo repo, đếm lệnh gọi (`calls: list[str]`), và có `fail_with: Exception | None` để giả lỗi.
- Cần thêm `_request` hỗ trợ body JSON (hiện chỉ có method/bearer/url) mà giữ nguyên hành vi cũ.

- [ ] **Step 1:** Viết test (mỗi test một hành vi, dùng `MockTransport` ghi lại request): `test_find_issue_by_label_returns_lowest_number_including_closed`, `test_find_issue_by_label_none_when_missing`, `test_create_issue_posts_title_body_labels`, `test_update_issue_patches_state_and_fields`, `test_ensure_label_ignores_already_exists`, `test_issue_calls_use_installation_token_of_the_repo`, `test_github_error_on_403_rate_limit_has_vietnamese_message`.
- [ ] **Step 2:** Chạy `uv run pytest tests/test_github_issues.py -q` → FAIL (chưa có hàm).
- [ ] **Step 3:** Cài đặt các hàm theo Interfaces, dùng REST: `GET /repos/{repo}/issues?labels=<label>&state=all&per_page=100`, `POST /repos/{repo}/issues`, `PATCH /repos/{repo}/issues/{n}`, `POST /repos/{repo}/labels`. Mã 403/429 báo `GitHubError` với câu tiếng Việt nói rõ là bị giới hạn lượt gọi.
- [ ] **Step 4:** Mở rộng `FakeGitHub` cho khớp Protocol; chạy toàn bộ test → xanh, `mypy` sạch.
- [ ] **Step 5:** Commit `feat(core): GitHubClient tạo, tìm, sửa issue và label`

---

### Task 2: Soạn nội dung issue từ test case

**Files:**
- Create: `backend/app/core/github/issue_format.py`
- Test: `backend/tests/test_issue_format.py`

**Interfaces:**
- Produces: `IssueContent(title: str, body: str, labels: list[str])`; `render_issue(case: TestCase, *, screen_name: str = "") -> IssueContent` (hàm thuần, không gọi mạng); hằng `ISSUE_LABEL = "test-case"`; `case_label(case_id: str) -> str` trả `"tc:TC-000123"`; `status_label(status: TestCaseStatus) -> str` trả `"status:APPROVED"`.

- [ ] **Step 1:** Viết test: `test_title_has_case_id_prefix`, `test_labels_are_test_case_case_id_and_status`, `test_body_lists_steps_with_expected_and_expected_result`, `test_body_never_contains_test_data` (case có `test_data="matkhau123"` → chuỗi đó không xuất hiện), `test_body_never_contains_creator_emails` (case có `created_by="an@x.com"`), `test_body_with_vietnamese_and_markdown_special_chars_is_kept_readable` (ký tự `|`, backtick, `#` trong tiêu đề không phá định dạng), `test_body_has_marker_with_case_id_and_version` (dòng ẩn `<!-- tc:TC-000123 v3 -->` để người đọc biết bản nào), `test_very_long_case_body_is_truncated_under_github_limit` (giới hạn 65536 ký tự, cắt kèm ghi chú).
- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Cài `render_issue`; thân issue: màn hình, mức độ, ưu tiên, điều kiện tiên quyết, danh sách bước đánh số (mỗi bước có "Kết quả mong đợi" nếu có), kết quả mong đợi, dòng trạng thái; **bỏ `test_data`, `created_by`, `updated_by`**. Hành động của bước tự do là chữ người dùng nhập nên phải thoát ký tự Markdown nguy hiểm (`@` nhắc tên người, dùng chèn `​` sau `@` hoặc bọc trong khối code).
- [ ] **Step 4:** Test xanh, `mypy`/`ruff` sạch. **Step 5:** Commit `feat(core): soạn nội dung issue từ test case, không lộ test_data và email`

---

### Task 3: IssueSyncer và đồng bộ nền

**Files:**
- Create: `backend/app/core/services/issue_sync.py`
- Test: `backend/tests/test_issue_sync.py`

**Interfaces:**
- Consumes: Task 1 (`GitHubClient`, `IssueInfo`), Task 2 (`render_issue`, `case_label`, `ISSUE_LABEL`, `status_label`); `Project` (`repo_full_name`, `archived`); `TestCase`, `TestCaseStatus`.
- Produces:
  - `IssueSyncer(github: GitHubClient | None)` với `sync_case(project: Project, case: TestCase, *, screen_name: str = "") -> SyncResult`, `SyncResult = Literal["created", "updated", "closed", "reopened", "skipped"]`.
  - `class IssueSink(Protocol): def sync_case(self, project: Project, case: TestCase, *, screen_name: str = "") -> None`.
  - `BackgroundIssueSync(syncer: IssueSyncer, *, executor: Executor | None = None)` cài `IssueSink`: nộp việc vào **một** `ThreadPoolExecutor(max_workers=1)` (hoặc executor tiêm vào, để test chạy đồng bộ), **bắt mọi ngoại lệ**, log cảnh báo kèm mã case (không kèm nội dung case).
- Quy tắc `sync_case` (mỗi dòng có test):
  1. `github is None` hoặc dự án `archived` → `skipped`.
  2. Case `DRAFT`/`IN_REVIEW` mà **chưa có issue** → `skipped` (không tạo issue cho case chưa duyệt).
  3. Case `APPROVED` chưa có issue → `ensure_label` cho `test-case`, `tc:<id>`, `status:*` rồi `create_issue` → `created`.
  4. Đã có issue → `update_issue` (nội dung và label trạng thái mới; gỡ label `status:*` cũ). Trạng thái `DEPRECATED` → `state="closed"` (`closed`); issue đang đóng mà case không `DEPRECATED` → `state="open"` (`reopened`); còn lại `updated`.
  5. Tìm issue luôn bằng `find_issue_by_label(repo, case_label(id))`; **không** lưu số issue ở đâu cả.
  6. Repo chưa cài App (`GitHubError` 404) → ném lên để `BackgroundIssueSync` log; `IssueSyncer` không nuốt lỗi (để "Đồng bộ lại" báo được).

- [ ] **Step 1:** Viết test với `FakeGitHub`: `test_approved_case_without_issue_creates_one_with_labels`, `test_draft_case_without_issue_is_skipped`, `test_second_sync_updates_not_duplicates` (gọi hai lần → `len(issues)==1`), `test_status_change_replaces_status_label`, `test_deprecated_closes_and_restore_reopens`, `test_no_github_configured_is_skipped`, `test_archived_project_is_skipped`, `test_background_swallows_github_error_and_logs_case_id_only` (dùng `caplog`; log không chứa tiêu đề case), `test_same_case_id_in_two_projects_gets_issues_in_their_own_repos`.
- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Cài theo Interfaces. **Step 4:** Xanh, `mypy`/`ruff`. **Step 5:** Commit `feat(core): đồng bộ test case sang GitHub issue, chạy nền và không làm hỏng việc lưu`

---

### Task 4: Gắn đồng bộ vào các thao tác case

**Files:**
- Modify: `backend/app/core/services/test_cases.py` (`TestCaseService.__init__` nhận `issue_sync: IssueSink | None = None` và `project: Project | None`; gọi trong `_save` và `approve_many`), `backend/app/api/services.py` (`Services.issue_sync: IssueSink | None = None`; `build_services` dựng `BackgroundIssueSync(IssueSyncer(github))` khi có GitHub), `backend/app/api/routers/test_cases.py` (`_service_for` truyền `services.issue_sync` và `project`)
- Test: `backend/tests/test_test_case_service.py` (thêm), `backend/tests/test_test_cases_api.py` (thêm)

**Interfaces:**
- Consumes: `IssueSink` (Task 3). `conftest.py` thêm fixture `issue_sink` (bản ghi lệnh gọi) và truyền vào `Services`.
- Quy tắc: sau khi `_test_cases.save` và `_audit` thành công (case đã nằm trên Sheet), gọi `issue_sync.sync_case(project, saved, screen_name=<tên màn hình>)`. Gọi cho **mọi** thao tác đổi case: tạo (bỏ qua nhờ quy tắc 2), sửa nội dung, gửi duyệt, duyệt, duyệt hàng loạt (một lần gọi cho **mỗi** case được duyệt, không gọi cho case bị bỏ qua), trả lại, ngừng dùng, khôi phục. Mọi ngoại lệ từ `issue_sync` bị bắt trong service (phòng khi sink không phải bản nền).

- [ ] **Step 1:** Viết test: `test_approve_syncs_issue_for_the_saved_case`, `test_batch_approve_syncs_each_approved_case_once_and_not_skipped_ones`, `test_edit_of_approved_case_syncs_with_status_draft`, `test_return_deprecate_restore_each_sync`, `test_sync_failure_does_not_fail_the_save_nor_duplicate_the_case` (sink ném `GitHubError`; API trả 200, `list_cases()` vẫn đúng một case), `test_sync_receives_screen_name_not_creator_email`, `test_service_without_sink_still_works` (các test cũ không đổi).
- [ ] **Step 2:** Chạy → FAIL. **Step 3:** Cài; trong `_save` dùng cùng kiểu "cố gắng hết sức" như `_refresh_status` (bắt `Exception`, `logger.warning(..., exc_info=True)`). **Step 4:** Chạy toàn bộ backend → xanh (273+ test cũ vẫn qua). **Step 5:** Commit `feat(core): đồng bộ issue sau khi duyệt hoặc sửa test case`

---

### Task 5: "Đồng bộ lại issue" (QA Lead/Admin)

**Files:**
- Modify: `backend/app/api/routers/test_cases.py` (route `POST /sync-issues`), `backend/app/core/services/test_cases.py` (`sync_issues(user) -> SyncIssuesResult`), `frontend/lib/use-test-cases.ts` (`useSyncIssues`), `frontend/app/(app)/projects/[projectId]/test-cases/page.tsx` (nút), `frontend/messages/vi.json`, `frontend/lib/api/{openapi.json,schema.d.ts,types.ts}` (chạy `npm run gen:api`)
- Test: `backend/tests/test_test_cases_api.py`, `frontend/lib/use-test-cases.test.tsx`

**Interfaces:**
- Backend: `POST /api/projects/{project_id}/test-cases/sync-issues` (quyền `REVIEW_TEST_CASE`) → `{"created": int, "updated": int, "closed": int, "reopened": int, "skipped": int, "failed": [{"case_id": str, "reason": str}]}`. Chạy **đồng bộ trong request**, **tuần tự**, dừng nhẹ khi gặp lỗi hạn mức (`GitHubError` có "giới hạn" → trả những gì đã làm kèm `failed`), tối đa `MAX_BATCH_SIZE = 200` case một lượt. Dùng `IssueSyncer` trực tiếp (không qua luồng nền) để báo được lỗi.

- [ ] **Step 1:** Test backend: `test_sync_issues_requires_review_permission` (tester 403), `test_sync_issues_creates_missing_issues_for_approved_cases_only`, `test_sync_issues_is_idempotent_second_call_updates` (không tạo trùng), `test_sync_issues_reports_failures_per_case_and_continues`, `test_sync_issues_without_github_configured_is_503_with_vietnamese_message`.
- [ ] **Step 2:** Test frontend `useSyncIssues` gọi đúng endpoint và làm mới danh sách khi xong.
- [ ] **Step 3:** Cài; nút "Đồng bộ lại issue" ở trang danh sách case, chỉ hiện với người có `REVIEW_TEST_CASE`; sau khi xong hiện toast tóm tắt "Tạo N, cập nhật M, lỗi K". Chạy `npm run gen:api`.
- [ ] **Step 4:** Xanh cả hai phía. **Step 5:** Commit `feat: nút Đồng bộ lại issue cho QA Lead và Admin`

---

### Task 6: API cho agent ghi kết quả (token riêng)

**Files:**
- Modify/restore: lấy từ tag `m4-playwright-v1` đúng các file sau (giữ nguyên nội dung, kèm test của chúng):
  `git checkout m4-playwright-v1 -- backend/app/core/models/run.py backend/app/core/repositories/runs.py backend/tests/test_run_repository.py` và thêm `SheetTable.append_many` (+ test `tests/test_sheet_table_append_many.py`) từ cùng tag. **Không** lấy `run_queue.py`, worker, router `runs.py`, frontend runs.
  Nhớ rằng `RunRepository.create` đòi `IdGenerator` (đã có) và thêm `runs`/`results` vào `ProjectScope`/`scope_for`.
- Create: `backend/app/api/routers/agent.py`; Modify: `backend/app/settings.py` (`agent_api_token: str = ""`), `backend/app/main.py`, `.env.example`
- Test: `backend/tests/test_agent_results_api.py`

**Interfaces:**
- `POST /api/agent/projects/{project_id}/results` với header `Authorization: Bearer <AGENT_API_TOKEN>`; body `{"results": [{"test_case_id": str, "status": "PASS"|"FAIL"|"BLOCKED"|"INCONCLUSIVE", "reason": str = "", "failed_step": int | None, "evidence": str = ""}]}` (tối đa 200 phần tử, `reason`/`evidence` tối đa 2000 ký tự).
- Hành vi: tạo **một run** (`triggered_by="codex-agent"`, `status` rồi đóng ngay `COMPLETED`, `total/passed/failed` đúng) và ghi các `Result` bằng một lần `append_batch`; mã kết quả `"<mã run>-<mã case>"`. Trả `{"run_id": str, "written": int, "ignored": [{"test_case_id": str, "reason": str}]}`. Case không tồn tại **trong dự án đó** hoặc không `APPROVED` → vào `ignored`, không ghi.
- Bảo mật: `agent_api_token` rỗng → endpoint trả **404** (coi như không tồn tại); sai hoặc thiếu token → **401** `{"detail": "Token không hợp lệ"}`; so sánh bằng `secrets.compare_digest`; token **không bao giờ** xuất hiện trong log hay response. Route này **không dùng cookie** và không cho đọc gì ngoài việc ghi kết quả. Dự án đã lưu trữ → 409. `RunRepository.create` ném `RunInProgressError` khi đang có run chưa xong (hai agent gửi cùng lúc) → trả **409** `Đang có một lần ghi kết quả khác, hãy thử lại`; thêm test `test_two_posts_at_same_time_second_gets_409` (dùng `gateway.after_next_read`).

- [ ] **Step 1:** Restore các file từ tag; chạy test của chúng → xanh (xác nhận chúng đứng vững trên nhánh này).
- [ ] **Step 2:** Viết test API: `test_disabled_when_token_not_configured_is_404`, `test_wrong_or_missing_token_is_401`, `test_valid_token_writes_run_and_results_in_one_batch` (kiểm `gateway.calls.count("append:Results") == 1`), `test_unknown_case_id_is_ignored_with_reason`, `test_case_of_other_project_is_ignored` (cùng mã `TC-000001` ở hai dự án: chỉ ghi vào dự án trong URL), `test_not_approved_case_is_ignored`, `test_token_never_in_response_or_logs`, `test_over_200_results_is_422`, `test_archived_project_is_409`.
- [ ] **Step 3:** Cài; thêm `AGENT_API_TOKEN=` vào `.env.example` kèm chú thích (chuỗi ngẫu nhiên dài, không commit). **Step 4:** Chạy toàn bộ → xanh. **Step 5:** Commit `feat(api): agent ghi kết quả chạy test bằng token riêng`

---

### Task 7: Tài liệu cấu hình Codex và cập nhật ghi chú

**Files:**
- Create: `docs/codex-agent.md`; Modify: `README.md`, `DECISIONS.md`, `HANDOFF.md`

- [ ] **Step 1:** Viết `docs/codex-agent.md` (tiếng Việt đơn giản): (1) bật GitHub MCP cho Codex (**kiểm tra cú pháp cấu hình trong tài liệu chính thức của Codex ở thời điểm làm, không đoán**), cấp token GitHub chỉ có quyền `Issues` (đọc/ghi) trên repo app; (2) cho phép Codex chạy đúng vài lệnh (`npm install`, `npm run dev`, `npx playwright install chromium`, `npx playwright test --reporter=json`) trong thư mục riêng, không cho đọc `.env`; (3) **prompt mẫu** gồm: liệt kê issue có label `test-case` và `status:APPROVED`, đọc repo để biết cách chạy app, viết kịch bản Playwright, chạy, lấy **kết quả từ báo cáo JSON** (không tự phán), comment lên đúng issue (PASS/FAIL, bước lỗi), rồi gọi `POST /api/agent/projects/{id}/results` kèm `Authorization: Bearer ...`; (4) mẫu lệnh `curl` và ví dụ body; (5) lưu ý repo công khai, không dán mật khẩu vào issue/comment.
- [ ] **Step 2:** README: mục "Codex chạy test" trỏ tới tài liệu; `.env.example` đã có `AGENT_API_TOKEN`. `DECISIONS.md`: thêm quyết định (issue chỉ tạo khi duyệt; tìm bằng label, không cột Sheet; đồng bộ nền tuần tự và best-effort; `test_data`/email không vào issue; token agent riêng, tắt khi không cấu hình; kết quả vào cả issue lẫn `Results`). `HANDOFF.md`: cập nhật "Đang ở đâu" và việc còn dở.
- [ ] **Step 3:** Chạy bộ test đầy đủ cả hai phía, ghi số test thực tế. **Step 4:** Commit `docs: hướng dẫn cấu hình Codex và ghi quyết định đồng bộ issue`
- [ ] **Step 5 (không code, cần chủ dự án):** chạy thử thật với repo `hieupt-ht/126CQH01-NHOM-14` (cần GitHub App đã cài vào repo đó với quyền Issues đọc/ghi): duyệt một case, xem issue xuất hiện; mở Codex theo `docs/codex-agent.md`. Ghi trung thực kết quả, kể cả phần không chạy được. **Không push, không tạo PR; hỏi chủ dự án.**

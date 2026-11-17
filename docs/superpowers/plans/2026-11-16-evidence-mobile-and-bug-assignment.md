# Bằng chứng ảnh/video, test mobile, giao bug cho dev — Kế hoạch triển khai

> **Cho agent thực hiện:** BẮT BUỘC dùng superpowers:subagent-driven-development (khuyên dùng) hoặc superpowers:executing-plans để làm từng task. Các bước dùng ô `- [ ]` để đánh dấu.

**Mục tiêu:** Mở một kết quả FAIL là thấy bước sai, ảnh của bước đó, video cả lần chạy, môi trường và dev được giao; tester chỉ đường cho Codex bằng ảnh/video; test được web, Android, iOS.

**Kiến trúc:** Không thêm sheet, chỉ thêm cột vào cuối các tab có sẵn (app tự thêm tiêu đề cột thiếu). Ảnh/video nằm trên Cloudinary: backend ký upload, trình duyệt/Codex đẩy thẳng file lên, backend chỉ nhận link thuộc đúng cloud của mình. Mọi việc gọi GitHub/Cloudinary sau khi ghi Sheet đều "cố gắng hết sức": lỗi chỉ ghi log, không làm hỏng việc lưu.

**Công nghệ:** Python 3.12, FastAPI, pydantic, httpx, Redis, Google Sheets; Next.js 16, TypeScript, Tailwind, next-intl, react-hook-form + zod, vitest.

**Spec:** `docs/superpowers/specs/2026-11-16-evidence-mobile-and-bug-assignment-design.md` — người làm đọc spec trước, kế hoạch này chỉ ghi các quyết định spec để ngỏ.

## Ràng buộc chung

- `CLOUDINARY_API_SECRET` chỉ ở backend `.env`; không xuất hiện trong response, log, issue, frontend, máy Codex.
- Backend chỉ nhận `Media.url` bắt đầu bằng `https://res.cloudinary.com/<CLOUDINARY_CLOUD_NAME>/`. Sai thì 422 `{"detail": "Link ảnh/video không thuộc kho Cloudinary của app"}`.
- Tối đa 5 `Media` mỗi bước và 5 cho cả case. Ảnh ≤ 10MB, video ≤ 100MB và ≤ 3 phút.
- `folder` upload: `ai-test-runner/<project_id>/<guide|evidence>`.
- Nhãn issue: `platform: web`, `platform: android`, `platform: ios`, `bug: cần sửa`; giữ `needs-rerun`, `test: pass`, `test: fail`.
- Giữ bằng chứng của **5** kết quả gần nhất mỗi case.
- Ảnh cắt từ video: tối đa **6** khung, tại giây 1, 3, 5, 7, 9, 11.
- Comment sửa case: `📝 Case đã sửa lên v<N>: <danh sách trường đổi>`.
- Tooltip nút duyệt bị mờ: `Dự án đang tắt bước duyệt`. API duyệt/trả lại khi tắt: 409, cùng câu.
- Dòng nhắc trong form: `Đừng chụp mật khẩu hoặc thông tin cá nhân; ảnh có thể hiện trong issue công khai.`
- Issue không chứa `test_data` hay email. Không thêm lượt đọc Sheet dày (≈60 lượt/phút).
- TDD từng task; comment code tiếng Việt; chuỗi giao diện ở `frontend/messages/vi.json`; sửa API thì chạy `cd frontend && npm run gen:api`.
- Commit: Conventional Commits, mô tả tiếng Việt, heredoc Git Bash, kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Không push, không PR.
- Kiểm tra cuối mỗi đợt: `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check`; `cd frontend && npx vitest run && npm run typecheck && npm run lint`.

## Điểm cần soi khi review

Spec không nói rõ nhưng người dùng sẽ gặp; mỗi dòng đã có test ở task ghi trong ngoặc.

1. **Sheet thật của dự án cũ chưa có cột mới** → app phải tự thêm tiêu đề ở cuối, không báo `MissingColumnsError`, không đụng cột lạ (Task 1).
2. **Sửa case làm mất nhãn kết quả trên issue**: `update_issue` hiện ghi đè toàn bộ nhãn, nên `needs-rerun`, `test: fail`, `bug: cần sửa` bị xoá mỗi lần sửa case → giữ mọi nhãn không do app sinh từ case (Task 14).
3. **Codex gửi lại kết quả cũ dạng `evidence: "https://..."`** → vẫn nhận, hiện như một link (Task 15).
4. **Link Cloudinary của cloud khác hoặc `http://`** trong case hay kết quả → 422, không ghi Sheet (Task 2, 11, 15).
5. **Tắt công tắc khi có 0 case `IN_REVIEW`** hoặc bật lại → không ghi Sheet thừa, không tạo AuditLog rỗng (Task 6).

---

## Đợt 1 — Dữ liệu và mô hình

### Task 1: Tự thêm cột còn thiếu vào cuối tiêu đề

**Files:**
- Modify: `backend/app/core/sheets/table.py`, `backend/app/core/bootstrap.py`, `backend/app/main.py`
- Test: `backend/tests/test_sheet_table.py`, `backend/tests/test_bootstrap.py`

**Interfaces:**
- Produces: `SheetTable.ensure_columns() -> list[str]` (trả tên cột vừa thêm); `upgrade_project_spreadsheets(projects: ProjectRepository, gateway: SheetsGateway) -> None` trong `bootstrap.py`.

- [x] **Bước 1: Viết test đỏ**

```python
def test_ensure_columns_appends_missing_at_end_and_keeps_unknown(gateway):
    gateway.add_tab("S", "T", ["id", "la", "name"])          # "la" là cột lạ
    table = SheetTable(gateway, "S", "T", ["id", "name", "platform", "regression"])
    assert table.ensure_columns() == ["platform", "regression"]
    assert gateway.get_values("S", "T!1:1")[0] == ["id", "la", "name", "platform", "regression"]
    assert table.ensure_columns() == []                       # chạy lần hai không đổi gì

def test_bootstrap_project_upgrades_old_tabs(gateway):
    gateway.add_tab("S", "TestCases", TEST_CASE_COLUMNS[:15])  # tiêu đề cũ
    bootstrap_project_spreadsheet(gateway, "S")
    assert gateway.get_values("S", "TestCases!1:1")[0][-1] == "requirement_ref"

def test_upgrade_skips_archived_and_logs_errors(...):
    # dự án lưu trữ không bị đọc; một dự án lỗi quyền không chặn dự án sau
```

- [x] **Bước 2:** `uv run pytest tests/test_sheet_table.py tests/test_bootstrap.py -q` → FAIL (chưa có `ensure_columns`).
- [x] **Bước 3:** Viết `ensure_columns`: đọc hàng 1, cột thiếu nối vào cuối, ghi lại bằng `update_row(..., 1, header)` (1 lượt đọc + tối đa 1 lượt ghi). `_ensure_tabs` gọi `ensure_columns()` thay cho `check_columns()`. `upgrade_project_spreadsheets` chạy cho mọi dự án chưa lưu trữ, mỗi dự án bọc `try/except Exception` + `logger.warning`; gọi trong `lifespan` của `main.py` ngay sau `bootstrap_system_spreadsheet`.
- [x] **Bước 4:** Chạy lại test → PASS; chạy cả bộ backend.
- [x] **Bước 5:** Commit `feat(sheets): tự thêm cột mới vào cuối tiêu đề khi khởi động`.

### Task 2: Kiểu `Media` và kiểm tra link Cloudinary

**Files:**
- Create: `backend/app/core/models/media.py`
- Modify: `backend/app/settings.py` (thêm `cloudinary_cloud_name`, `cloudinary_api_key`, `cloudinary_api_secret`, mặc định `""`), `.env.example` (chỉ tên biến, không giá trị)
- Test: `backend/tests/test_media.py`

**Interfaces:**
- Produces:
  - `class MediaKind(StrEnum): IMAGE="image"; VIDEO="video"`
  - `class Media(BaseModel): kind: MediaKind; url: str (max 500); public_id: str (max 300); note: str = "" (max 200)` — validator chỉ nhận `https://res.cloudinary.com/...`.
  - `MediaList = Annotated[list[Media], Field(max_length=5)]`
  - `class ForeignMediaError(ValueError)`
  - `ensure_own_cloud(items: Iterable[Media], cloud_name: str) -> None` — cloud_name rỗng thì báo `ForeignMediaError("Chưa cấu hình Cloudinary")`.

- [x] **Bước 1: Test đỏ**

```python
def test_media_rejects_non_cloudinary_and_http():
    for url in ["http://res.cloudinary.com/c/a.png", "https://evil.com/a.png"]:
        with pytest.raises(ValidationError):
            Media(kind="image", url=url, public_id="x")

def test_ensure_own_cloud():
    ok = Media(kind="image", url="https://res.cloudinary.com/mine/image/upload/a.png", public_id="a")
    other = ok.model_copy(update={"url": "https://res.cloudinary.com/other/image/upload/a.png"})
    ensure_own_cloud([ok], "mine")
    with pytest.raises(ForeignMediaError, match="không thuộc kho Cloudinary"):
        ensure_own_cloud([other], "mine")
    with pytest.raises(ForeignMediaError, match="Chưa cấu hình Cloudinary"):
        ensure_own_cloud([ok], "")
    ensure_own_cloud([], "")   # không có media thì không cần cấu hình
```

- [x] **Bước 2:** Chạy → FAIL. **Bước 3:** Viết code. **Bước 4:** PASS.
- [x] **Bước 5:** Commit `feat(media): thêm kiểu Media và kiểm tra link Cloudinary`.

### Task 3: Cột mới của `Projects` và `Screens`

**Files:**
- Modify: `backend/app/core/sheets/schema.py`, `backend/app/core/models/project.py`, `backend/app/core/models/screen.py`, `backend/app/core/repositories/projects.py`, `backend/app/core/repositories/screens.py`
- Test: `backend/tests/test_project_repository.py`, `backend/tests/test_screens_api.py` (phần repository)

**Interfaces:**
- Produces: `Project.android_app_id: str = ""`, `Project.ios_bundle_id: str = ""`, `Project.require_review: bool = False`; `Screen.dev_owner: str = ""`. Cột thêm vào **cuối** `PROJECT_COLUMNS` / `SCREEN_COLUMNS`.

- [x] **Bước 1: Test đỏ** — dòng Sheet có ô mới để trống đọc ra `require_review is False`, `android_app_id == ""`, `dev_owner == ""`; ghi `require_review=True` rồi đọc lại ra `"TRUE"`/`True`.
- [x] **Bước 2–4:** FAIL → viết `_to_record`/`_from_record` (bool theo kiểu `archived`) → PASS.
- [x] **Bước 5:** Commit `feat(models): thêm cột app id, require_review và dev_owner`.

### Task 4: Trường mới của test case

**Files:**
- Modify: `backend/app/core/models/test_case.py`, `backend/app/core/sheets/schema.py`, `backend/app/core/repositories/test_cases.py`
- Test: `backend/tests/test_test_case_repository.py`

**Interfaces:**
- Produces:
  - `class Platform(StrEnum): WEB, ANDROID, IOS`; `class TestType(StrEnum): FUNCTIONAL, UI`
  - `TestStep.guide_media: MediaList = []`
  - `TestCaseContent` thêm: `platform: Platform = WEB`, `test_type: TestType = FUNCTIONAL`, `regression: bool = False`, `start_point: str = ""` (max 500), `guide_media: MediaList = []`, `postcondition: str = ""` (max 2000), `requirement_ref: str = ""` (max 200)
  - Cột Sheet thêm cuối `TEST_CASE_COLUMNS` theo thứ tự: `platform, test_type, regression, start_point, guide_media_json, postcondition, requirement_ref`. `steps` vẫn là JSON, mỗi bước thêm khoá `guide_media`.
  - `media_of(case: TestCaseContent) -> list[Media]` — mọi media của case (cả bước), dùng cho kiểm tra cloud và dọn file.

- [x] **Bước 1: Test đỏ**

```python
def test_old_row_reads_defaults(repo_with_old_row):
    case = repo.get("TC-000001")
    assert (case.platform, case.test_type, case.regression) == (Platform.WEB, TestType.FUNCTIONAL, False)
    assert case.guide_media == [] and case.steps[0].guide_media == []

def test_round_trip_new_fields(repo):
    # tạo case có platform=ANDROID, regression=True, 1 ảnh ở bước 1, 1 video cả case → đọc lại bằng nhau

def test_step_media_limit():
    with pytest.raises(ValidationError):
        TestStep(action="a", guide_media=[IMG] * 6)
```

- [x] **Bước 2–4:** FAIL → viết → PASS. Sửa `contentOf` phía frontend để typecheck vẫn qua (chỉ thêm trường, chưa thêm giao diện).
- [x] **Bước 5:** `npm run gen:api`, commit `feat(test-cases): thêm nền tảng, loại test, regression và ảnh hướng dẫn`.

### Task 5: Trường mới của `Runs` và `Results`

**Files:**
- Modify: `backend/app/core/models/run.py`, `backend/app/core/sheets/schema.py`, `backend/app/core/repositories/runs.py`, các chỗ đang dùng `Result.screenshot` (`agent.py`, `results.py`, `result_issue_sync.py`)
- Test: `backend/tests/test_run_repository.py`

**Interfaces:**
- Produces:
  - `RunScope.regression_only: bool = False`, `RunScope.case_ids: list[str] = []` (case thuộc Run regression; Task 23 dùng)
  - `Run.build_version: str = ""` (cột mới `build_version`)
  - `class Evidence(BaseModel): video: Media | None = None; screenshots: list[Media] = [] (max 20); legacy_url: str | None = None; pruned: bool = False`
  - `class StepResult(BaseModel): step_no: int (ge=1); status: Literal["PASS","FAIL","SKIPPED"]; actual: str = "" (max 1000); screenshot: Media | None = None`
  - `Result` bỏ `screenshot`, thêm: `evidence: Evidence`, `step_results: list[StepResult] = []`, `actual_result: str = ""`, `environment: str = ""`, `executed_by: str = ""`, `case_version: int | None = None`, `dev_owner: str = ""`, `defect_url: str = ""`
  - Cột Results thêm cuối: `step_results_json, actual_result, environment, executed_by, case_version, dev_owner, defect_url`

- [x] **Bước 1: Test đỏ**

```python
def test_legacy_evidence_still_reads(results_repo_with_row('{"screenshot": "https://x/a.png"}')):
    assert results.list_all()[0].evidence == Evidence(legacy_url="https://x/a.png")

def test_round_trip_step_results_and_video(...)
def test_empty_new_cells_default(...)   # step_results == [], case_version is None
```

- [x] **Bước 2–4:** FAIL → viết → PASS (cả bộ backend phải qua sau khi đổi `screenshot` → `evidence.legacy_url`).
- [x] **Bước 5:** Commit `feat(runs): lưu kết quả từng bước, video và môi trường chạy`.

---

## Đợt 2 — Công tắc duyệt, sửa case đã gửi, lịch sử

### Task 6: Ghi nhiều dòng một lượt và công tắc `require_review`

**Files:**
- Modify: `backend/app/core/sheets/gateway.py` (+ `tests/fakes.py`), `backend/app/core/sheets/table.py`, `backend/app/core/repositories/test_cases.py`, `backend/app/api/routers/projects.py`, `backend/app/core/services/projects.py`
- Test: `backend/tests/test_sheet_table.py`, `backend/tests/test_projects_api.py`

**Interfaces:**
- Produces:
  - `SheetsGateway.update_rows(spreadsheet_id, tab, rows: dict[int, list[str]]) -> None` (Google `values.batchUpdate`, một lời gọi)
  - `SheetTable.update_many(found: list[FoundRecord] | list[tuple[int, Record]], ...)` — một lượt đọc tab + một lượt ghi
  - `TestCaseRepository.approve_all_in_review(actor: str) -> list[TestCase]` — trong khoá tab, đọc thẳng Sheet, đổi mọi `IN_REVIEW` → `APPROVED`, tăng version, ghi một lượt; rỗng thì không ghi
  - `UpdateProjectRequest` thêm `android_app_id: str | None`, `ios_bundle_id: str | None` (max 200, chỉ `[A-Za-z0-9._-]`), `require_review: bool | None`. Quyền: Admin hoặc QA Lead thành viên dự án (khác `MANAGE_PROJECTS` hiện chỉ Admin → thêm `Action.MANAGE_PROJECT_SETTINGS` trong `permissions.py`).
  - `ProjectService.update_project(..., require_review=...)`: chuyển `True → False` thì gọi `approve_all_in_review`, ghi AuditLog `AUTO_APPROVE` cho từng case, rồi `issue_sync.sync_case` từng case (BackgroundIssueSync, một luồng).

- [x] **Bước 1: Test đỏ**

```python
def test_turning_review_off_approves_in_review_once(lead, project, gateway):
    # 2 case IN_REVIEW, 1 DRAFT
    r = lead.patch(f"/api/projects/{project.id}", json={"require_review": False})
    assert r.status_code == 200
    assert statuses() == {"TC-000001": "APPROVED", "TC-000002": "APPROVED", "TC-000003": "DRAFT"}
    assert gateway.batch_update_calls == 1

def test_turning_off_with_nothing_in_review_writes_nothing(...)    # Review Focus 5
def test_turning_on_does_not_touch_cases(...)
def test_tester_cannot_change_require_review(...)  # 403
def test_app_ids_reject_spaces(...)                # 422
```

- [x] **Bước 2–4:** FAIL → viết → PASS.
- [x] **Bước 5:** Commit `feat(projects): công tắc cần QA duyệt và app id mobile`.

### Task 7: Gửi là duyệt luôn khi tắt bước duyệt

**Files:**
- Modify: `backend/app/core/services/test_cases.py`
- Test: `backend/tests/test_test_case_service.py`, `backend/tests/test_test_cases_api.py`

**Interfaces:**
- Consumes: `Project.require_review` (Task 3). `TestCaseService` đã nhận `project`.
- Produces: `REVIEW_OFF = "Dự án đang tắt bước duyệt"`; `TestCaseService.review_enabled -> bool` (không có project thì `True`, giữ hành vi cũ cho test cũ).

- [x] **Bước 1: Test đỏ**

```python
def test_submit_goes_straight_to_approved_when_review_off(...):
    saved = service.transition(tester, "TC-000001", CaseAction.SUBMIT, version=1)
    assert saved.status == TestCaseStatus.APPROVED
    assert issue_sink.synced[-1].status == TestCaseStatus.APPROVED
    assert notifier.submitted == []            # không báo "chờ duyệt"

@pytest.mark.parametrize("path", ["approve", "return"])
def test_review_endpoints_409_when_off(lead, project, path):
    r = lead.post(f".../TC-000001/{path}", json={"version": 2, "comment": "x"})
    assert r.status_code == 409 and r.json()["detail"] == "Dự án đang tắt bước duyệt"

def test_approve_batch_409_when_off(...)
def test_review_on_keeps_old_flow(...)         # SUBMIT → IN_REVIEW
```

- [x] **Bước 2–4:** FAIL → viết (SUBMIT có đích `APPROVED` khi tắt; AuditLog ghi `SUBMIT` với diff `DRAFT→APPROVED`) → PASS.
- [x] **Bước 5:** Commit `feat(test-cases): gửi case là duyệt luôn khi dự án tắt bước duyệt`.

### Task 8: Sửa case đã gửi tại chỗ, comment và `needs-rerun`

**Files:**
- Modify: `backend/app/core/services/test_cases.py`, `backend/app/core/services/issue_sync.py`, `backend/app/api/routers/test_cases.py`
- Test: `backend/tests/test_test_case_service.py`, `backend/tests/test_issue_sync.py`

**Interfaces:**
- Consumes: `request_rerun_on_issue` (có sẵn), `ResultRepository.list_all`.
- Produces:
  - `RERUN_FIELDS = {"steps", "expected_result", "start_point", "platform", "guide_media"}` (đổi `guide_media` trong bước cũng tính, vì nằm trong `steps`)
  - `IssueSink.note_case_edited(project: Project, case: TestCase, *, changed: list[str], needs_rerun: bool) -> None` — `IssueSyncer` comment `📝 Case đã sửa lên v<N>: <changed nối bằng ", ">` rồi, nếu `needs_rerun`, gọi `request_rerun_on_issue`. `BackgroundIssueSync` đẩy vào **cùng** executor một luồng để luôn chạy sau `sync_case`.
  - `TestCaseService.__init__(..., has_results: Callable[[str], bool] | None = None)` — router truyền hàm đọc `scope.results.list_all()` một lần (chỉ gọi khi cần, tức case `APPROVED` và đổi trường thuộc `RERUN_FIELDS`).
  - Tên trường trong comment dùng nhãn tiếng Việt: `CHANGED_FIELD_LABELS = {"title": "Tiêu đề", "steps": "Các bước", "expected_result": "Kết quả mong đợi", "platform": "Nền tảng", "start_point": "Điểm bắt đầu", "guide_media": "Ảnh/video hướng dẫn", ...}` (đủ mọi trường `TestCaseContent`).

- [x] **Bước 1: Test đỏ**

```python
def test_edit_approved_keeps_status_when_review_off(...):
    saved = service.update_content(tester, "TC-000001", version=2, content=changed_title)
    assert saved.status == TestCaseStatus.APPROVED and saved.version == 3
    assert sink.edits == [("TC-000001", ["Tiêu đề"], False)]

def test_edit_steps_with_results_requests_rerun(...):
    has_results = lambda case_id: True
    ...
    assert sink.edits[-1][2] is True

def test_edit_steps_without_results_no_rerun(...)
def test_edit_with_review_on_resets_to_draft(...)     # hành vi cũ

def test_background_note_runs_after_sync(fake_github):
    # executor đồng bộ trong test: thứ tự calls là update rồi comments:create
    assert "📝 Case đã sửa lên v3: Các bước" in comment_bodies()
```

- [x] **Bước 2–4:** FAIL → viết → PASS.
- [x] **Bước 5:** Commit `feat(test-cases): sửa case đã gửi tại chỗ và báo lên issue`.

### Task 9: Giao diện công tắc, nút duyệt mờ, lịch sử

**Files:**
- Modify: `frontend/app/(app)/projects/[projectId]/settings/page.tsx`, `frontend/components/test-cases/review-actions.tsx`, `frontend/components/test-cases/bulk-approve-bar.tsx`, `frontend/components/test-cases/history-panel.tsx`, `frontend/components/test-cases/case-form.tsx`, `frontend/messages/vi.json`
- Test: `frontend/components/test-cases/review-actions.test.tsx` (mới), `frontend/components/test-cases/history-panel.test.tsx` (mới)

**Interfaces:**
- Consumes: `Project.require_review`, `android_app_id`, `ios_bundle_id` (sau `gen:api`).
- Produces: prop `reviewDisabled: boolean` cho `ReviewActions` và `BulkApproveBar`.

- [x] **Bước 1: Test đỏ** — `ReviewActions reviewDisabled` render nút "Duyệt"/"Trả lại" có `disabled` và tooltip "Dự án đang tắt bước duyệt"; `HistoryPanel` hiện dòng `v3 · 16/11/2026 14:05 · Lan · Các bước, Nền tảng` (giờ Việt Nam, tên trường dịch từ `CHANGED_FIELD_LABELS` phía frontend trong `lib/test-cases/history.ts`).
- [x] **Bước 2:** `npx vitest run components/test-cases` → FAIL.
- [x] **Bước 3:** Viết. Trang Cài đặt: `Switch` "Cần QA duyệt" + hai ô app id (Admin/QA Lead). Form: nút "Lưu và gửi duyệt" đổi chữ thành "Gửi" khi tắt duyệt; cảnh báo `resetWarning` chỉ hiện khi bật duyệt.
- [x] **Bước 4:** PASS + typecheck + lint.
- [x] **Bước 5:** Commit `feat(frontend): công tắc duyệt, nút duyệt mờ và lịch sử phiên bản`.

---

## Đợt 3 — Upload Cloudinary và form 2 cột

### Task 10: Ký upload và xoá file Cloudinary

**Files:**
- Create: `backend/app/core/media/__init__.py`, `backend/app/core/media/cloudinary.py`, `backend/app/api/routers/media.py`
- Modify: `backend/app/api/routers/agent.py` (thêm route ký cho agent, tách `_check_token` dùng chung), `backend/app/api/services.py`, `backend/app/main.py`
- Test: `backend/tests/test_cloudinary.py`, `backend/tests/test_media_api.py`

**Interfaces:**
- Produces:
  - `class SignedUpload(BaseModel): cloud_name, api_key, timestamp: int, signature, folder, public_id, allowed_formats: str, resource_type: Literal["image","video"], max_bytes: int, upload_url: str`
  - `CloudinarySigner(cloud_name, api_key, api_secret, *, now=time.time, token=secrets.token_urlsafe)`; `.sign(project_id: str, purpose: Literal["guide","evidence"], kind: MediaKind) -> SignedUpload`
  - Chữ ký theo quy tắc Cloudinary: các tham số ký (`allowed_formats`, `folder`, `public_id`, `timestamp`) sắp xếp theo tên, nối `k=v` bằng `&`, nối thêm `api_secret`, lấy SHA-1 hex. `public_id` = `token(16)`.
  - `allowed_formats`: ảnh `jpg,jpeg,png,webp,gif`; video `mp4,mov,webm`. `max_bytes`: 10_485_760 / 104_857_600.
  - `CloudinaryClient.destroy(public_id: str, kind: MediaKind) -> None` (POST `https://api.cloudinary.com/v1_1/<cloud>/<kind>/destroy`, ký `public_id`+`timestamp`)
  - `MediaJanitor(client | None)`: `.delete(items: list[Media]) -> None` chạy nền một luồng, lỗi chỉ `logger.warning`; client `None` thì bỏ qua. Gắn vào `Services.media_janitor` và `Services.cloudinary_signer` (`None` khi thiếu cấu hình).
  - Route: `POST /api/projects/{project_id}/media/sign` body `{kind, purpose: "guide"}` (quyền `EDIT_TEST_CASE`); `POST /api/agent/projects/{project_id}/media/sign` body `{kind}` (token agent, `purpose` luôn `evidence`). Chưa cấu hình → 503 "Chưa cấu hình Cloudinary".

- [x] **Bước 1: Test đỏ**

```python
def test_signature_matches_cloudinary_rule():
    signer = CloudinarySigner("c", "k", "s", now=lambda: 1700000000, token=lambda n: "abc")
    signed = signer.sign("PRJ-0001", "guide", MediaKind.IMAGE)
    raw = "allowed_formats=jpg,jpeg,png,webp,gif&folder=ai-test-runner/PRJ-0001/guide&public_id=abc&timestamp=1700000000s"
    assert signed.signature == hashlib.sha1(raw.encode()).hexdigest()
    assert "s" not in signed.model_dump().values()       # không lộ secret

def test_sign_endpoint_never_returns_secret(member, project, settings_with_cloudinary):
    body = member.post(f"/api/projects/{project.id}/media/sign", json={"kind": "video", "purpose": "guide"}).json()
    assert "api_secret" not in body and settings.cloudinary_api_secret not in json.dumps(body)

def test_agent_sign_requires_token(...)                 # 401 khi sai token
def test_sign_503_when_not_configured(...)
def test_janitor_logs_and_swallows_errors(caplog)
```

- [x] **Bước 2–4:** FAIL → viết → PASS.
- [x] **Bước 5:** `gen:api`; commit `feat(media): ký upload Cloudinary cho tester và agent`.

### Task 11: Kiểm tra cloud và dọn file khi lưu case

**Files:**
- Modify: `backend/app/core/services/test_cases.py`, `backend/app/api/routers/test_cases.py`
- Test: `backend/tests/test_test_case_service.py`

**Interfaces:**
- Consumes: `media_of`, `ensure_own_cloud`, `MediaJanitor.delete`.
- Produces: `TestCaseService.__init__(..., cloud_name: str = "", janitor: MediaJanitor | None = None)`. `ForeignMediaError` đổi thành `InvalidTestCaseError` (422) ở `create`/`update_content`. Sau khi lưu thành công, media có trong bản cũ mà không còn trong bản mới (so theo `public_id`) được gửi `janitor.delete`. AuditLog diff thay mỗi `Media` bằng `{"kind", "note"}` (lịch sử chỉ giữ chữ).

- [x] **Bước 1: Test đỏ** — case có ảnh `a`,`b`; lưu với chỉ `b` → `janitor.deleted == ["a"]`; ảnh cloud khác → `InvalidTestCaseError` và Sheet không đổi; diff AuditLog không chứa `res.cloudinary.com`.
- [x] **Bước 2–4:** FAIL → viết → PASS.
- [x] **Bước 5:** Commit `feat(test-cases): kiểm tra link ảnh và dọn file Cloudinary khi sửa case`.

### Task 12: Thư viện upload và ô chọn ảnh/video (frontend)

**Files:**
- Create: `frontend/lib/media/upload.ts`, `frontend/lib/media/upload.test.ts`, `frontend/components/media/media-picker.tsx`, `frontend/components/media/media-picker.test.tsx`, `frontend/components/media/media-lightbox.tsx`

**Interfaces:**
- Produces:
  - `checkFile(file: File, kind: MediaKind): string | null` — trả khoá lỗi `tooLarge` / `badType` / null
  - `videoDuration(file: File): Promise<number>` (đọc metadata bằng thẻ `<video>`), từ chối > 180 giây với khoá `tooLong`
  - `uploadMedia(file: File, opts: { projectId: string; onProgress?: (percent: number) => void; signal?: AbortSignal }): Promise<Media>` — xin chữ ký rồi `XMLHttpRequest` POST `upload_url` (để có tiến độ); trả `{kind, url: secure_url, public_id, note: ""}`
  - `<MediaPicker value={Media[]} onChange max={5} projectId />` — thumbnail ảnh (bấm mở lightbox), video có `<video controls>`, thanh tiến độ khi đang tải, nút xoá, ô ghi chú ngắn; hết chỗ thì ẩn nút "+".

- [x] **Bước 1: Test đỏ** — `checkFile` với ảnh 11MB → `tooLarge`; `.exe` → `badType`; `uploadMedia` với XHR giả gọi `onProgress(50)` và trả đúng `secure_url`; `MediaPicker` có 5 mục thì không còn nút "Thêm ảnh/video"; bấm xoá gọi `onChange` thiếu mục đó.
- [x] **Bước 2–4:** `npx vitest run lib/media components/media` FAIL → viết → PASS.
- [x] **Bước 5:** Commit `feat(frontend): upload ảnh/video lên Cloudinary có xem trước`.

### Task 13: Form tạo/sửa case 2 cột

**Files:**
- Modify: `frontend/components/test-cases/case-form.tsx`, `frontend/components/test-cases/steps-editor.tsx`, `frontend/lib/test-cases/form-schema.ts`, `frontend/app/(app)/projects/[projectId]/test-cases/new/page.tsx`, `frontend/app/(app)/projects/[projectId]/test-cases/[caseId]/page.tsx`, `frontend/messages/vi.json`
- Test: `frontend/lib/test-cases/form-schema.test.ts`, `frontend/components/test-cases/case-form.test.tsx` (mới)

**Interfaces:**
- Consumes: `MediaPicker` (Task 12), trường mới của `TestCaseContent`.

- [x] **Bước 1: Test đỏ** — schema nhận đủ trường mới với mặc định (`platform: "WEB"`, `regression: false`); `CaseForm` render ô Nền tảng, Loại, Regression, Bắt đầu tại, dòng nhắc an toàn ảnh, mục thu gọn "Điều kiện, dữ liệu, ..." chứa precondition/test_data/postcondition/requirement_ref; khi đang upload thì nút Lưu/Gửi bị khoá.
- [x] **Bước 2:** FAIL.
- [x] **Bước 3:** Bố cục theo sơ đồ 5.10: bỏ `max-w-3xl` ở hai trang; thanh nút `sticky top-0`; `lg:grid-cols-2`, khung cao `lg:h-[calc(100dvh-<chiều cao topbar+thanh nút>)]`, chỉ cột "Các bước" có `overflow-y-auto`; dưới `lg` một cột. Mỗi bước có `MediaPicker` nhỏ; cột trái có `MediaPicker` cho cả case.
- [ ] **Bước 4:** PASS + typecheck + lint. Mở trình duyệt ở 1366×768 xác nhận không cuộn cả trang (ghi lại trong báo cáo task). _(test, typecheck, lint đã qua; CHƯA mở trình duyệt thật ở 1366×768 vì cần đăng nhập Google và Sheet thật — chủ dự án kiểm tra giúp)_
- [x] **Bước 5:** Commit `feat(frontend): form test case 2 cột có ảnh/video hướng dẫn`.

---

## Đợt 4 — Nội dung issue

### Task 14: Issue có nền tảng, ảnh hướng dẫn, ảnh cắt từ video; giữ nhãn ngoài

**Files:**
- Create: `backend/app/core/media/frames.py`
- Modify: `backend/app/core/github/issue_format.py`, `backend/app/core/services/issue_sync.py`
- Test: `backend/tests/test_issue_format.py`, `backend/tests/test_issue_sync.py`, `backend/tests/test_media_frames.py`

**Interfaces:**
- Produces:
  - `FRAME_SECONDS = (1, 3, 5, 7, 9, 11)`; `video_frame_urls(media: Media) -> list[str]` — chèn `so_<giây>/` ngay sau `/video/upload/` và đổi đuôi thành `.jpg`; media không phải video trả `[]`
  - `platform_label(p: Platform) -> str` → `"platform: web"` …
  - `render_issue(case, *, project: Project | None = None, screen: Screen | None = None, ...)` thêm: dòng `- Phiên bản case: v<N>` (Codex gửi lại số này), `Nền tảng`, `Loại test`, `Regression: có/không`, `Điểm bắt đầu` (rỗng thì `screen.route`), `android_app_id` khi ANDROID / `ios_bundle_id` khi IOS; dưới mỗi bước liệt kê `![ghi chú](url)` cho ảnh và `Video: <url>` + `Ảnh cắt: <url1> <url2> …` cho video; mục `## Ảnh/video cho cả case`. Ghi chú đi qua `_safe_text`.
  - Nhãn: thêm `platform_label(case.platform)`.
  - `IssueSyncer.sync_case` khi cập nhật: nhãn mới = nhãn do app sinh + mọi nhãn cũ **không** bắt đầu bằng `status:` hoặc `platform:` (giữ `needs-rerun`, `test: fail`, `bug: cần sửa`, nhãn tay của người dùng).

- [ ] **Bước 1: Test đỏ**

```python
def test_video_frames():
    v = Media(kind="video", url="https://res.cloudinary.com/c/video/upload/v1/ai-test-runner/P/guide/x.mp4", public_id="x")
    assert video_frame_urls(v)[0] == "https://res.cloudinary.com/c/video/upload/so_1/v1/ai-test-runner/P/guide/x.jpg"
    assert len(video_frame_urls(v)) == 6

def test_issue_body_has_platform_and_app_id(): ...
def test_issue_never_contains_test_data_or_email(): ...   # giữ test cũ, thêm ảnh có note chứa email → bị chặn @
def test_update_keeps_result_labels(fake_github):          # Review Focus 2
    # issue đang có ["test-case","tc:TC-000001","status:APPROVED","platform: web","needs-rerun","test: fail"]
    # đổi platform sang ANDROID → nhãn có "platform: android", vẫn còn "needs-rerun","test: fail", mất "platform: web"
```

- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** Commit `feat(issues): thêm nền tảng, ảnh hướng dẫn và ảnh cắt từ video vào issue`.

---

## Đợt 5 — Kết quả từ Codex và trang Kết quả

### Task 15: API kết quả mở rộng

**Files:**
- Modify: `backend/app/api/routers/agent.py`
- Test: `backend/tests/test_agent_results_api.py`

**Interfaces:**
- Consumes: `Evidence`, `StepResult` (Task 5), `ensure_own_cloud`.
- Produces: `AgentResult` thêm `step_results: list[StepResult] = []` (max 50), `evidence: str | AgentEvidence = ""` (`AgentEvidence = {video: Media | None, screenshots: list[Media]}`; chuỗi cũ → `Evidence(legacy_url=...)` chỉ khi bắt đầu `https://`), `actual_result: str = ""` (max 2000), `environment: str = ""` (max 200), `executed_by: str = ""` (max 50), `case_version: int | None`. `AgentResultsRequest` thêm `build_version: str = ""` (max 50) — ghi vào Run mới. `Result.dev_owner` lấy từ `screen.dev_owner` lúc ghi (đọc `scope.screens.list_all()` một lần). Link sai cloud → 422 cho cả request, không tạo Run.

- [ ] **Bước 1: Test đỏ**

```python
def test_old_string_evidence_still_accepted(...):          # Review Focus 3
    post(results=[{**RESULT, "evidence": "https://example.com/a.png"}])
    assert stored().evidence.legacy_url == "https://example.com/a.png"

def test_new_evidence_and_steps_stored(...)
def test_foreign_cloud_rejected_and_no_run_created(...)     # 422, tab Runs không thêm dòng
def test_dev_owner_snapshot_from_screen(...)
def test_build_version_saved_on_run(...)
```

- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** Commit `feat(agent): nhận kết quả từng bước, video và môi trường`.

### Task 16: Giữ bằng chứng 5 lần chạy gần nhất

**Files:**
- Create: `backend/app/core/services/evidence_retention.py`
- Modify: `backend/app/api/routers/agent.py`
- Test: `backend/tests/test_evidence_retention.py`

**Interfaces:**
- Consumes: `SheetTable.update_many` (Task 6).
- Produces: `ResultRepository.mark_pruned(result_ids: list[str]) -> None` (ghi `evidence_json` = `{"pruned": true}` bằng một lượt `update_many`); `KEEP_RESULTS = 5`; `results_to_prune(results: list[Result], case_ids: set[str]) -> list[Result]` (hàm thuần: với mỗi case, sắp `created_at` giảm dần, bỏ 5 cái đầu, trả các kết quả còn media và chưa `pruned`); `prune_evidence(results_repo, janitor, case_ids) -> None` — đọc Results một lần, gọi `janitor.delete` cho mọi media (video, screenshots, ảnh từng bước), rồi `mark_pruned`. Gọi cuối `write_agent_results`, bọc `try/except` + log.

- [ ] **Bước 1: Test đỏ** — 6 kết quả của TC-1 → kết quả cũ nhất bị chọn; kết quả chỉ có `legacy_url` không bị chọn (không phải file của mình); đã `pruned` thì bỏ qua; lỗi janitor không làm request lỗi.
- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** Commit `feat(agent): dọn bằng chứng cũ, giữ 5 lần chạy gần nhất mỗi case`.

### Task 17: Comment kết quả có bảng từng bước

**Files:**
- Modify: `backend/app/core/services/result_issue_sync.py`
- Test: `backend/tests/test_github_issues.py` (hoặc file test comment hiện có)

**Interfaces:**
- Produces: `format_fail_comment` / `format_pass_comment` dùng `result.step_results` khi có (✅ PASS, ❌ FAIL, – SKIPPED hoặc thiếu bước), thêm cột "Thực tế"; dòng `**Ảnh bước lỗi:** [Mở ảnh](...)`, `**Video:** [Xem video](...)`, `**Môi trường:** ...`, `**Chạy với:** v<N>`. Không có `step_results` thì giữ cách suy từ `failed_step` như cũ. Link qua `_safe_evidence`.

- [ ] **Bước 1: Test đỏ** — bảng có 3 dòng `✅ / ❌ / –` đúng thứ tự; có link video; chữ "Thực tế" chứa email bị thay `[đã ẩn email]`.
- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** Commit `feat(issues): comment kết quả có bảng từng bước, ảnh và video`.

### Task 18: Script `upload_evidence` cho Codex

**Files:**
- Create: `backend/app/tools/upload_evidence.py`
- Test: `backend/tests/test_upload_evidence.py`

**Interfaces:**
- Produces: chạy `cd backend && uv run python -m app.tools.upload_evidence --project PRJ-0001 --file shot.png [--note "Bước 2"]` → in một dòng JSON `Media`. Đọc `AGENT_API_TOKEN` và `AI_TEST_RUNNER_URL` từ biến môi trường; thiếu thì thoát mã 2 với câu tiếng Việt. `kind` đoán theo đuôi file. Hàm `upload(path: Path, *, project_id: str, note: str, base_url: str, token: str, http: httpx.Client) -> dict`. Không in token kể cả khi lỗi.

- [ ] **Bước 1: Test đỏ** — `httpx.MockTransport`: gọi đúng `/api/agent/projects/PRJ-0001/media/sign` với `Authorization: Bearer t`, rồi POST file lên `upload_url`, trả `{"kind": "image", "url": secure_url, ...}`; lỗi 401 → thông báo không chứa token.
- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** Commit `feat(tools): script upload bằng chứng cho Codex`.

### Task 19: API Kết quả trả đủ thông tin và lọc

**Files:**
- Modify: `backend/app/api/routers/results.py`
- Test: `backend/tests/test_results_api.py`

**Interfaces:**
- Produces: `ResultItem` thêm `platform`, `regression`, `case_version`, `environment`, `executed_by`, `dev_owner`, `actual_result`, `step_results`, `evidence: Evidence`, `issue_url: str` (không gọi GitHub: dựng link tìm theo nhãn `https://github.com/<repo>/issues?q=label%3Atc%3A<case_id>`), `build_version`. Bỏ `evidence: str` cũ (frontend sửa cùng Task 20). Tham số lọc mới: `platform: Platform | None`, `run_id: str | None` (khi có: lấy kết quả của đúng Run đó thay vì mới nhất toàn dự án), `regression_only: bool = False`.

- [ ] **Bước 1: Test đỏ** — lọc `platform=ANDROID`; `run_id=RUN-0002` trả kết quả của run đó dù có run mới hơn; `regression_only=true` chỉ trả case `regression`.
- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** `gen:api`; commit `feat(results): trả kết quả từng bước, bằng chứng và bộ lọc mới`.

### Task 20: Bảng chi tiết kết quả (frontend)

**Files:**
- Create: `frontend/components/results/result-detail.tsx`, `frontend/components/results/result-detail.test.tsx`, `frontend/components/results/result-filters.tsx`
- Modify: `frontend/app/(app)/projects/[projectId]/results/page.tsx`, `frontend/lib/use-results.ts`, `frontend/messages/vi.json`
- Test: `frontend/app/(app)/projects/[projectId]/results/page.test.tsx`

**Interfaces:**
- Consumes: `ResultItem` mới, `MediaLightbox` (Task 12).

- [ ] **Bước 1: Test đỏ** — `ResultDetail` cho kết quả FAIL hiện tiêu đề `TC-000005 … FAIL · v2 · Pixel 7 / Android 14`, `Dev phụ trách: @nguyenvana`, `Chạy bởi codex-windows`, trình phát video, bảng bước (ảnh mở lightbox), bước không chạy hiện "Không chạy"; `evidence.pruned` → "Bằng chứng đã được dọn"; `legacy_url` → một link "Mở bằng chứng". Trang lọc theo nền tảng/Run/regression gửi đúng query.
- [ ] **Bước 2:** FAIL.
- [ ] **Bước 3:** Bấm một kết quả mở bảng bên phải (`Dialog` kiểu sheet, toàn màn hình dưới `sm`). Dùng lại `safeEvidenceUrl` có sẵn cho link.
- [ ] **Bước 4:** PASS + typecheck + lint.
- [ ] **Bước 5:** Commit `feat(frontend): bảng chi tiết kết quả có ảnh từng bước và video`.

---

## Đợt 6 — Dev phụ trách

### Task 21: Ô dev phụ trách ở Màn hình

**Files:**
- Modify: `backend/app/api/routers/screens.py`, `backend/app/core/services/screens.py`, `frontend/components/screens/screen-form-dialog.tsx`, `frontend/app/(app)/projects/[projectId]/screens/page.tsx`, `frontend/messages/vi.json`
- Test: `backend/tests/test_screens_api.py`, `frontend/components/screens/screen-form-dialog.test.tsx` (mới)

**Interfaces:**
- Produces: `GitHubUsername = Annotated[str, Field(max_length=39, pattern=r"^$|^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")]`; tự bỏ `@` ở đầu trước khi kiểm tra. `CreateScreenRequest.dev_owner = ""`, `UpdateScreenRequest.dev_owner: GitHubUsername | None`.

- [ ] **Bước 1: Test đỏ** — `"@nguyenvana"` lưu thành `"nguyenvana"`; `"a b"` → 422; tester không sửa được (403 như hiện nay).
- [ ] **Bước 2–4:** FAIL → viết → PASS. Danh sách màn hình hiện cột "Dev phụ trách".
- [ ] **Bước 5:** `gen:api`; commit `feat(screens): thêm dev phụ trách cho màn hình`.

### Task 22: Gán issue cho dev khi FAIL

**Files:**
- Modify: `backend/app/core/github/client.py`, `backend/tests/fakes.py`, `backend/app/core/services/result_issue_sync.py`
- Test: `backend/tests/test_github_client.py`, `backend/tests/test_github_issues.py`

**Interfaces:**
- Produces:
  - `GitHubClient.add_assignees(repo_full_name: str, issue_number: int, assignees: list[str]) -> None` (POST `/repos/{repo}/issues/{n}/assignees`). GitHub trả 201 nhưng bỏ qua người không hợp lệ → so `assignees` trong response, thiếu thì báo `GitHubError("Không gán được @<tên>")`.
  - `BUG_LABEL = "bug: cần sửa"`, màu `b60205`.
  - `sync_result_issue` FAIL + `result.dev_owner`: `add_assignees`, thêm `BUG_LABEL` vào nhãn, comment có dòng `Giao cho @<dev_owner>` (tạo trực tiếp, không qua `_safe_text`). Gán lỗi → comment có dòng `⚠️ Không gán được issue cho @<dev_owner>, hãy kiểm tra tên GitHub và quyền repo.` và vẫn cập nhật nhãn. PASS: bỏ `BUG_LABEL`, không bỏ người được gán.

- [ ] **Bước 1: Test đỏ** — FAIL có dev → `fake.assignees[1] == ["nguyenvana"]`, nhãn có `bug: cần sửa`; PASS sau đó → nhãn mất `bug: cần sửa`, `assignees` giữ nguyên; `fail_assign_with=GitHubError` → comment có câu cảnh báo, kết quả vẫn ghi (API trả 200).
- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** Commit `feat(issues): gán issue FAIL cho dev phụ trách màn hình`.

---

## Đợt 7 — Chạy bộ regression

### Task 23: Run regression trong repository

**Files:**
- Modify: `backend/app/core/repositories/runs.py`
- Test: `backend/tests/test_run_repository.py`

**Interfaces:**
- Produces:
  - `RunRepository.create_regression(*, triggered_by: str, branch: str, build_version: str, case_ids: list[str]) -> Run` — trạng thái `RUNNING`, `scope.regression_only=True`, `scope.case_ids=case_ids`, `total=len(case_ids)`, không kiểm tra run đang chạy.
  - `active()` và kiểm tra trong `create()` **bỏ qua** run có `scope.regression_only`.
  - `RunRepository.add_results(run_id: str, results: list[Result], *, all_case_ids_done: Callable[[Run], bool]) -> Run` — trong khoá run: cộng dồn `passed/failed`, nếu mọi `case_ids` đã có kết quả thì `COMPLETED` + `finished_at`.
  - `RunRepository.finish(run_id: str) -> Run` — `RUNNING → COMPLETED`; run thường hoặc đã xong → `InvalidRunStateError`.

- [ ] **Bước 1: Test đỏ** — có run regression `RUNNING` thì `create()` vẫn tạo được run thường; `add_results` hai lần cộng dồn đúng; đủ case thì tự `COMPLETED`; gửi lại cùng case hai lần không đếm `total` hai lần (đếm theo case khác nhau).
- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** Commit `feat(runs): thêm run regression cộng dồn kết quả`.

### Task 24: API chạy bộ regression và gắn kết quả theo `run_id`

**Files:**
- Create: `backend/app/api/routers/regression.py`
- Modify: `backend/app/core/services/rerun_request.py`, `backend/app/api/routers/agent.py`, `backend/app/api/routers/results.py`, `backend/app/main.py`
- Test: `backend/tests/test_regression_api.py`, `backend/tests/test_agent_results_api.py`

**Interfaces:**
- Produces:
  - `POST /api/projects/{project_id}/regression-runs` body `{build_version: str (1–50)}` quyền `REVIEW_TEST_CASE` → 201 `Run`. Case chọn: `regression=True` và `APPROVED`. Không có case nào → 400 "Không có case regression nào đã duyệt". Gắn `needs-rerun` cho từng case qua `request_rerun_on_issue(..., run_id=run.id)` chạy trên executor một luồng (dùng lại của `BackgroundIssueSync`).
  - `POST /api/projects/{project_id}/regression-runs/{run_id}/finish` → `Run`.
  - `format_rerun_comment(user_name, requested_at, *, run_id: str | None = None)` thêm dòng `Mã lần chạy: RUN-0007 — gửi kèm "run_id" khi báo kết quả.`
  - `AgentResultsRequest.run_id: str | None`: có thì dùng `add_results` (run phải là regression `RUNNING`, không thì 409 "Lần chạy này đã kết thúc hoặc không phải lần chạy regression"); case không thuộc `scope.case_ids` bị cho vào `ignored`.
  - `results_for_project` coi run regression `RUNNING` như run đã có kết quả (dùng `started_at` khi chưa có `finished_at`) để kết quả hiện ngay.

- [ ] **Bước 1: Test đỏ** — tạo regression với 2 case regression + 1 case thường → `total == 2`, 2 comment rerun có `RUN-0001`; agent gửi `run_id` hai lần mỗi lần một case → run `COMPLETED`, `passed+failed == 2`; `run_id` của run thường → 409; tester gọi tạo → 403.
- [ ] **Bước 2–4:** FAIL → viết → PASS.
- [ ] **Bước 5:** `gen:api`; commit `feat(regression): chạy bộ regression theo bản build`.

### Task 25: Nút "Chạy bộ regression" (frontend)

**Files:**
- Create: `frontend/components/results/regression-dialog.tsx`, `frontend/components/results/regression-dialog.test.tsx`
- Modify: `frontend/app/(app)/projects/[projectId]/results/page.tsx`, `frontend/components/results/result-filters.tsx`, `frontend/lib/use-results.ts`, `frontend/messages/vi.json`

- [ ] **Bước 1: Test đỏ** — hộp thoại bắt nhập bản build (rỗng thì khoá nút), gửi đúng body; sau khi tạo, bộ lọc Run chọn sẵn run mới; nút "Kết thúc" chỉ hiện cho run regression `RUNNING` và chỉ với QA Lead/Admin.
- [ ] **Bước 2–4:** FAIL → viết → PASS + typecheck + lint.
- [ ] **Bước 5:** Commit `feat(frontend): nút chạy bộ regression ở trang Kết quả`.

---

## Đợt 8 — Tài liệu và chạy thử thật

### Task 26: Tài liệu Codex cho hai máy

**Files:**
- Modify: `docs/codex-agent.md`, `HANDOFF.md`, `.env.example`

- [ ] **Bước 1:** Viết lại `docs/codex-agent.md`: phần cài **Windows** (Java 17+, `adb`, Maestro CLI, Maestro MCP trong Codex, bật Gỡ lỗi USB, Playwright) và **Mac** (Xcode + Simulator, Java 17+, Maestro CLI/MCP, cài `.app` lên Simulator); biến môi trường `AGENT_API_TOKEN`, `AI_TEST_RUNNER_URL`; quy tắc **một phiên Codex mỗi máy**.
- [ ] **Bước 2:** Hai prompt: Windows chỉ lấy issue mở có `platform: web` hoặc `platform: android`; Mac chỉ `platform: ios`. Prompt yêu cầu: chụp ảnh mỗi bước và upload bằng `upload_evidence`; quay video (`recordVideo` / `adb shell screenrecord` — lưu ý giới hạn 3 phút của screenrecord / `xcrun simctl io booted recordVideo`); gửi `case_version` từ dòng "Phiên bản case" trong issue, `run_id` nếu comment chạy lại có mã, `environment`, `executed_by` (`codex-windows`/`codex-mac`), `step_results`.
- [ ] **Bước 3:** Cập nhật `HANDOFF.md` (việc dở số 2 đã xong, số test mới). `.env.example` thêm ba biến `CLOUDINARY_*` rỗng.
- [ ] **Bước 4:** Chạy cả hai bộ test (không đổi code, chỉ xác nhận).
- [ ] **Bước 5:** Commit `docs: hướng dẫn Codex cho máy Windows và Mac`.

### Task 27: Chạy thử thật (chủ dự án cùng làm)

Không có code; làm trên `hieupt-ht/ShopHub` sau khi chủ dự án điền `CLOUDINARY_*` vào `.env`.

- [ ] Web: tạo case có ảnh hướng dẫn, tắt duyệt, bấm Gửi → issue có ảnh và nhãn `platform: web`; Codex Windows chạy → trang Kết quả có ảnh từng bước + video.
- [ ] Android (điện thoại thật): case FAIL → issue được gán cho dev, nhãn `bug: cần sửa`; Chạy lại → PASS → nhãn bỏ.
- [ ] iOS (Mac Simulator): một case PASS có video.
- [ ] Regression: tạo run với bản build, chạy hai case, run tự `COMPLETED`.
- [ ] Ghi kết quả và vấn đề gặp phải vào `HANDOFF.md`; commit `docs: ghi kết quả chạy thử web, Android, iOS`.

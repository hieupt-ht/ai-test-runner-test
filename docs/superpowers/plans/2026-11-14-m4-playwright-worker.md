# M4 — Worker chạy test bằng Playwright: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** QA Lead bấm "Chạy" trên các case `APPROVED`; một worker chạy trên máy của chủ dự án tự bật app, đăng nhập, thực hiện các bước tự động bằng Playwright và ghi PASS/FAIL/BLOCKED (kèm bước lỗi và ảnh chụp) vào Sheet.

**Architecture:** Xây trên M3. `TestStep` có thêm trường tuỳ chọn `auto` (trong JSON cột `steps`). Backend thêm kho `Runs`/`Results` (tab đã có), `RunService` + router `/runs`, hàng đợi Redis. Worker là tiến trình riêng `python -m app.worker`, chạy thẳng trên máy (không Docker), lấy job từ Redis, đọc cấu hình app từ `worker-projects.json`, chạy từng case trong một ngữ cảnh trình duyệt mới dùng lại phiên đăng nhập, ghi kết quả theo lô. Frontend thêm phần "Tự động" vào form bước và tab "Chạy test".

**Tech Stack:** Như M3 + `playwright` (Python, Chromium) cho worker. Frontend không thêm thư viện.

**Spec:** `docs/superpowers/specs/2026-11-14-m4-playwright-worker-design.md` (thay mục 7.7 và 7.8 của `2026-11-12-ai-test-runner-design.md`; mục 9 và 7.9 của spec gốc vẫn áp dụng)

## Global Constraints

- Làm trên nhánh `feature/m4-playwright-worker`. Không push, không tạo PR khi chủ dự án chưa đồng ý.
- Commit theo Conventional Commits (type tiếng Anh, mô tả tiếng Việt có dấu), message viết bằng heredoc trong Git Bash, kết thúc bằng dòng `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Giữ quy tắc M1–M3: chỉ `gateway.py` gọi Google; ánh xạ Sheet theo tên cột; chuỗi giao diện nằm trong `frontend/messages/vi.json`; lỗi API là `{"detail": "<câu tiếng Việt>"}`; `mypy --strict`, `ruff check`, TypeScript strict, ESLint sạch.
- Giá trị bước tự động (spec mục 4): `type` ∈ `goto`/`fill`/`click`/`select`/`see_text`/`not_see_text`/`url_is`; `target.by` ∈ `text`/`label`/`css`; `value` và `target.value` tối đa 500 ký tự. **Không thêm cột Sheet**; case cũ không có `auto` vẫn đọc được.
- Trạng thái run: `QUEUED` → `RUNNING` → `COMPLETED`/`FAILED`/`CANCELLED`. Trạng thái kết quả: `PASS`/`FAIL`/`BLOCKED`/`INCONCLUSIVE`. Mỗi dự án **một run đang chạy** (`QUEUED` hoặc `RUNNING`); tạo thêm trả **409** `Dự án đang có một lần chạy chưa xong`.
- Chỉ case `APPROVED` được chạy. Số case tối đa mỗi run: `max_cases_per_run` (mặc định 200), vượt thì 422.
- Quyền dùng sẵn: tạo/huỷ run = `Action.TRIGGER_RUN`; xem run, kết quả, ảnh = `Action.VIEW_PROJECT`. Không thêm `Action` mới.
- Timeout: mỗi bước 10 giây, mỗi case 120 giây (đổi `case_timeout_seconds` mặc định từ 300 xuống 120), chờ app lên 120 giây. Cấu hình qua env.
- Ghi kết quả theo lô: mỗi 10 case hoặc mỗi 30 giây, bằng **một** lời gọi `append_rows`. Worker chỉ ghi `Runs` và `Results`.
- Cấu hình app và tài khoản test chỉ ở `worker-projects.json` (gitignore), **không** vào Sheet, API, log. Worker không bao giờ chạy lệnh lấy từ test case.
- Ảnh chụp lưu ở `artifacts/<run_id>/<test_case_id>.png` (gitignore); `Results.evidence_json` chỉ chứa `{"screenshot": "<run_id>/<test_case_id>.png"}`.
- Next.js 16 khác bản cũ: trước khi thêm route `runs/page.tsx` đọc `frontend/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/` (đặc biệt `page.md`) và nhớ bọc `useSearchParams` trong `<Suspense>` nếu dùng.
- Ghi quyết định mới vào cuối `DECISIONS.md` ở Task 10 (đánh dấu **[Quyết định M4]**).

**[Quyết định M4]** (các lựa chọn của kế hoạch này, ghi vào `DECISIONS.md` ở Task 10):
1. Cấu hình app (`app_path`, `start_command`, `app_url`, tài khoản, `login_steps`) ở file `worker-projects.json` trên máy worker, không có API sửa.
2. Lý do run `FAILED` lưu ở Redis `run:<id>:note` (hết hạn sau 30 ngày), vì tab `Runs` không có cột lý do và không thêm cột.
3. Mã kết quả = `<run_id>-<test_case_id>` (ví dụ `RUN-0001-TC-000012`), không dùng bộ đếm, để ghi lô không tốn lượt đọc/ghi `Meta`.
4. Case có bước thiếu `auto` (dù chỉ một bước) → `BLOCKED`, ghi rõ bước nào thiếu. Lỗi của chính worker khi chạy một case → `INCONCLUSIVE`.
5. Chưa có thông báo cho các role; xem kết quả ở tab "Chạy test".

## Review Focus

1. **Worker bị tắt giữa run** → run kẹt `RUNNING`, khoá cả dự án mãi mãi. Khi worker khởi động, run `RUNNING` phải được đánh dấu `FAILED` ("Worker bị dừng giữa chừng"). Test ở Task 5.
2. **Case chỉ có một phần bước tự động** (bước 2 thiếu `auto`) → phải `BLOCKED` chứ không `PASS` vì các bước còn lại qua. Test ở Task 4.
3. **Huỷ run khi đang chạy** → dừng sau case hiện tại, kết quả đã chạy vẫn được ghi, app bị tắt, run `CANCELLED`. Test ở Task 5.
4. **Hai người bấm "Chạy" cùng lúc** → đúng một run được tạo, người kia nhận 409. Test ở Task 2 (kho) và Task 6 (API).
5. **App không lên (cổng bận, lệnh sai, quá giờ) hoặc đăng nhập lỗi** → run `FAILED` kèm lý do rõ, không ghi FAIL cho từng case, tiến trình app không bị bỏ sót. Test ở Task 3 và Task 5.

---

## File Structure

```
backend/app/
├── core/
│   ├── models/test_case.py        # + AutoType, TargetBy, AutoTarget, AutoStep; TestStep.auto
│   ├── models/run.py              # MỚI: RunStatus, ResultStatus, RunScope, Run, Result
│   ├── repositories/test_cases.py # lưu/đọc auto
│   ├── repositories/runs.py       # MỚI: RunRepository, ResultRepository
│   ├── run_queue.py               # MỚI: RunJob, RunQueue (Redis: hàng đợi, cờ huỷ, ghi chú)
│   ├── services/runs.py           # MỚI: RunService
│   └── sheets/table.py            # + SheetTable.append_many
├── api/
│   ├── routers/runs.py            # MỚI
│   ├── project_scope.py           # + runs, results
│   └── services.py                # + max_cases_per_run, artifacts_dir
├── worker/                        # MỚI (chạy ngoài Docker)
│   ├── __main__.py                # vòng lặp lấy job
│   ├── config.py                  # đọc worker-projects.json
│   ├── app_process.py             # bật/tắt app của dự án
│   ├── steps.py                   # thực hiện một bước tự động bằng Playwright
│   ├── case_runner.py             # chạy một case, đăng nhập, BLOCKED/PASS/FAIL
│   └── run_executor.py            # chạy cả run, ghi lô, huỷ, khôi phục
└── settings.py                    # + artifacts_dir, worker_config_path, app_start_timeout_seconds, step_timeout_ms
backend/tests/worker/              # test của worker (kèm trang web giả)
frontend/
├── lib/test-cases/{steps.ts,form-schema.ts}   # + auto
├── lib/{use-runs.ts,project-tabs.ts}          # MỚI / sửa
├── components/test-cases/{steps-editor.tsx,auto-step-fields.tsx,case-read-only.tsx}
├── components/runs/                           # MỚI
├── app/(app)/projects/[projectId]/runs/page.tsx
└── messages/vi.json
```

---

### Task 1: Bước tự động trong `TestStep` (backend)

**Files:**
- Modify: `backend/app/core/models/test_case.py`
- Modify: `backend/app/core/repositories/test_cases.py` (`_to_record`, `_from_record`)
- Test: `backend/tests/test_auto_step.py` (mới), `backend/tests/test_test_case_repository.py`

**Interfaces:**
- Produces (trong `test_case.py`):
  - `class AutoType(StrEnum)`: `GOTO="goto"`, `FILL="fill"`, `CLICK="click"`, `SELECT="select"`, `SEE_TEXT="see_text"`, `NOT_SEE_TEXT="not_see_text"`, `URL_IS="url_is"`
  - `class TargetBy(StrEnum)`: `TEXT="text"`, `LABEL="label"`, `CSS="css"`
  - `class AutoTarget(BaseModel)`: `by: TargetBy`, `value: str` (1..500)
  - `class AutoStep(BaseModel)`: `type: AutoType`, `target: AutoTarget | None = None`, `value: str = ""` (≤500)
  - `TestStep.auto: AutoStep | None = None`

- [ ] **Step 1: Viết test model** trong `test_auto_step.py`, mỗi quy tắc một test:
  - `test_click_needs_target` (click không target → `ValidationError`), `test_fill_and_select_need_target`
  - `test_goto_see_text_not_see_text_url_is_need_value` (value rỗng → lỗi); `test_goto_must_not_have_target` (và `see_text`, `not_see_text`, `url_is`)
  - `test_fill_may_have_empty_value` (fill rỗng hợp lệ, để xoá ô); `test_click_value_may_be_empty`
  - `test_value_over_500_chars_rejected`
  - `test_old_step_without_auto_loads`: `TestStep(action="a", expected="")` có `auto is None`
- [ ] **Step 2: Chạy** `cd backend && uv run pytest tests/test_auto_step.py -v` → FAIL (chưa có lớp).
- [ ] **Step 3: Cài `AutoType`, `TargetBy`, `AutoTarget`, `AutoStep`, `TestStep.auto`** trong `test_case.py`, dùng `model_validator(mode="after")` cho quy tắc target/value ở trên. Thông báo lỗi tiếng Việt, ví dụ `Bước "click" cần chọn phần tử cần bấm`.
- [ ] **Step 4: Test lưu/đọc** trong `test_test_case_repository.py`:
  - `test_auto_step_round_trips_through_sheet` (tạo case có `auto`, đọc lại bằng repo mới, bằng nhau)
  - `test_record_without_auto_loads` (dòng Sheet có `steps` = `[{"action":"a","expected":"b"}]` → `auto is None`)
  - `test_steps_without_auto_do_not_write_auto_key` (JSON ghi ra không có khoá `auto` khi không dùng)
- [ ] **Step 5: Sửa `_to_record`/`_from_record`** (`test_cases.py:51-80`): `steps` ghi bằng `step.model_dump(mode="json", exclude_none=True)` (giữ `ensure_ascii=False`); đọc vẫn `TestStep(**step)`.
- [ ] **Step 6: Chạy** `uv run pytest -q`, `uv run mypy app`, `uv run ruff check` → sạch (273 test cũ vẫn qua).
- [ ] **Step 7: Commit** `feat(core): thêm bước tự động tuỳ chọn vào bước test case`

---

### Task 2: Kho `Runs` / `Results` và hàng đợi Redis

**Files:**
- Create: `backend/app/core/models/run.py`, `backend/app/core/repositories/runs.py`, `backend/app/core/run_queue.py`
- Modify: `backend/app/core/sheets/table.py` (thêm `append_many`)
- Modify: `backend/app/api/project_scope.py` (thêm `runs: RunRepository`, `results: ResultRepository` vào `ProjectScope` và `scope_for`), `backend/app/api/services.py` (thêm `max_cases_per_run: int = 200`, `artifacts_dir: Path = Path("artifacts")` vào `Services`; `build_services` lấy từ `settings.max_cases_per_run` và `settings.artifacts_dir`; Task 3 thêm `artifacts_dir` vào `Settings`, nên làm Task 3 trước hoặc thêm trường đó ở đây)
- Test: `backend/tests/test_run_repository.py`, `backend/tests/test_run_queue.py`, `backend/tests/test_sheet_table.py`

**Interfaces:**
- Consumes: `Priority`, `Severity` (`models/test_case.py`); `IdGenerator.next_id(entity, prefix, digits=)`; `SheetTable`; `redis_lock`; `utc_now`, `to_iso`, `from_iso`.
- Produces:
  - `SheetTable.append_many(records: list[Record]) -> None` (một lời gọi `append_rows`; danh sách rỗng thì không gọi).
  - `models/run.py`: `RunStatus`, `ResultStatus` (giá trị như Global Constraints); `RunScope(screen_ids: list[str]=[], priorities: list[Priority]=[], severities: list[Severity]=[])`; `Run(id, triggered_by, scope: RunScope, branch, commit_sha, status, started_at: datetime, finished_at: datetime | None, total: int, passed: int, failed: int, tokens_used: int)`; `Result(id, run_id, test_case_id, status: ResultStatus, reason: str, failed_step: int | None, screenshot: str | None, created_at: datetime)`.
  - `class RunInProgressError(Exception)`, `class RunNotFoundError(Exception)`.
  - `RunRepository(gateway, spreadsheet_id, redis, project_id, *, lock_wait_seconds=5.0)` với: `create(*, triggered_by: str, scope: RunScope, branch: str, total: int) -> Run` (id `RUN-0001`, `digits=4`, entity `"run"`; trong khoá `lock:<project_id>:runs` đọc lại Sheet, có run `QUEUED`/`RUNNING` thì `RunInProgressError`), `get(run_id) -> Run | None`, `list_all() -> list[Run]` (mới nhất trước), `active() -> Run | None`, `save(run: Run) -> Run` (khoá `lock:<project_id>:run:<id>`), `claim(run_id) -> Run | None` (trong khoá: chỉ `QUEUED` → `RUNNING`, ngược lại `None`), `cancel_if_queued(run_id) -> bool` (trong cùng khoá: `QUEUED` → `CANCELLED`, đặt `finished_at`).
  - `ResultRepository(gateway, spreadsheet_id)`: `append_batch(results: list[Result]) -> None` (một lời gọi), `list_for_run(run_id) -> list[Result]`. Mã kết quả do người gọi đặt `f"{run_id}-{test_case_id}"`. Cột `issue_url`, `reviewed_by`, `review_note`, `tokens_used` ghi rỗng/0.
  - `run_queue.py`: `RunJob(project_id: str, run_id: str, case_ids: list[str])` (Pydantic); `RunQueue(redis)` với `push(job)`, `pop(timeout_seconds: int) -> RunJob | None` (khoá Redis `queue:runs`, `BLPOP`), `request_cancel(run_id)`, `is_cancelled(run_id) -> bool` (`run:<id>:cancel`), `set_note(run_id, text)`, `get_note(run_id) -> str` (`run:<id>:note`, hết hạn 30 ngày; rỗng nếu không có).

- [ ] **Step 1: Test `append_many`** (`test_sheet_table.py`): `test_append_many_writes_all_rows_in_one_call` (gateway giả ghi nhận đúng một lời gọi `append:<tab>`, đủ dòng), `test_append_many_empty_does_nothing`.
- [ ] **Step 2: Test kho** (`test_run_repository.py`, dùng `FakeSheetsGateway` với tab `Runs`, `Results`, `Meta` có header từ `PROJECT_TABS`):
  - `test_create_run_is_queued_with_sequential_ids`
  - `test_second_create_while_active_is_rejected` (cả khi run đầu `QUEUED` lẫn `RUNNING`); `test_create_allowed_after_completed`
  - `test_two_creates_at_same_time_only_one_wins` (dùng `gateway.after_next_read` để chen request thứ hai giữa lúc đọc và ghi, như `test_assignment_races.py`)
  - `test_claim_only_from_queued` (lần hai trả `None`); `test_cancel_if_queued_blocks_later_claim`
  - `test_run_scope_round_trips` (cột `scope` lưu JSON)
  - `test_results_append_batch_and_list_for_run` (kết quả của hai run không lẫn)
- [ ] **Step 3: Test hàng đợi** (`test_run_queue.py`, `fakeredis`): `test_push_pop_fifo`, `test_pop_timeout_returns_none`, `test_cancel_flag`, `test_note_round_trip`, `test_note_missing_is_empty`.
- [ ] **Step 4: Chạy** các file test trên → FAIL.
- [ ] **Step 5: Cài** `append_many`, `models/run.py`, `repositories/runs.py`, `run_queue.py` theo Interfaces. `Run.commit_sha` ghi rỗng ở M4. `started_at` = lúc tạo run.
- [ ] **Step 6: Chạy** `uv run pytest -q`, `uv run mypy app`, `uv run ruff check` → sạch.
- [ ] **Step 7: Commit** `feat(core): thêm kho Runs, Results và hàng đợi run bằng Redis`

---

### Task 3: Cấu hình app của worker và bật/tắt app

**Files:**
- Create: `backend/app/worker/__init__.py`, `backend/app/worker/config.py`, `backend/app/worker/app_process.py`
- Modify: `backend/app/settings.py`, `.gitignore` (thêm `worker-projects.json`, `artifacts/`)
- Test: `backend/tests/worker/__init__.py`, `backend/tests/worker/test_config.py`, `backend/tests/worker/test_app_process.py`

**Interfaces:**
- Consumes: `AutoStep` (Task 1).
- Produces:
  - `Settings` thêm: `artifacts_dir: Path = Path("artifacts")`, `worker_config_path: Path = Path("worker-projects.json")`, `app_start_timeout_seconds: int = 120`, `step_timeout_ms: int = 10_000`; đổi `case_timeout_seconds` mặc định `120`.
  - `config.py`: `ProjectWorkerConfig(app_path: str, start_command: str, app_url: str, test_email: str, test_password: str, login_steps: list[AutoStep] = [])`; `class WorkerConfigError(Exception)`; `load_project_config(path: Path, project_id: str) -> ProjectWorkerConfig` (file thiếu, JSON hỏng, thiếu dự án, `app_path` không phải thư mục → `WorkerConfigError` với câu tiếng Việt nói rõ phải sửa gì và ở đâu; **thông báo lỗi không chứa mật khẩu**).
  - `app_process.py`: `class AppStartError(Exception)`; `running_app(config: ProjectWorkerConfig, *, timeout_seconds: float) -> ContextManager[None]`: chạy `start_command` (qua shell) trong `app_path`, chờ `app_url` trả lời bằng `httpx` (mọi mã HTTP < 500 coi là đã lên), thoát khối thì **tắt cả cây tiến trình** (Windows: `taskkill /PID <pid> /T /F`; hệ khác: `start_new_session=True` + `os.killpg`). Lệnh thoát sớm hoặc quá giờ → `AppStartError` (có đuôi 20 dòng cuối của output để dễ sửa) và vẫn dọn tiến trình.

- [ ] **Step 1: Test cấu hình** (`test_config.py`, `tmp_path`): `test_loads_project_config`, `test_missing_file_message_names_the_file`, `test_missing_project_message_names_project_id`, `test_invalid_json_is_config_error`, `test_missing_app_path_directory_is_config_error`, `test_error_messages_never_contain_password`, `test_login_steps_are_validated_as_auto_steps` (step `click` thiếu target → lỗi).
- [ ] **Step 2: Test bật/tắt app** (`test_app_process.py`; lệnh thật là `sys.executable -m http.server <port>` với cổng trống do test chọn):
  - `test_app_is_reachable_inside_block_and_stopped_after` (sau khối, cổng không còn trả lời)
  - `test_child_processes_are_killed` (lệnh là một script Python chạy `http.server` rồi tự sinh thêm một tiến trình con ngủ lâu và ghi PID con ra file trong `tmp_path`; sau khối, `psutil.pid_exists(pid_con)` phải là `False`; thêm `psutil` vào nhóm `dev` của `pyproject.toml`)
  - `test_command_that_exits_immediately_raises_app_start_error`
  - `test_never_ready_raises_after_timeout` (timeout 1 giây)
  - `test_port_already_in_use_raises` (cổng đã có người nghe, lệnh thoát lỗi → `AppStartError`)
- [ ] **Step 3: Chạy** → FAIL.
- [ ] **Step 4: Cài** `settings.py`, `config.py`, `app_process.py` theo Interfaces. Thông báo lỗi đúng giọng: `Chưa có cấu hình cho dự án PRJ-0001 trong worker-projects.json`.
- [ ] **Step 5: Chạy** `uv run pytest tests/worker -v` rồi `uv run pytest -q`, `uv run mypy app`, `uv run ruff check` → sạch.
- [ ] **Step 6: Commit** `feat(worker): đọc cấu hình app và tự bật/tắt app của dự án`

---

### Task 4: Thực hiện bước và chạy một case bằng Playwright

**Files:**
- Modify: `backend/pyproject.toml` (thêm `playwright>=1.49` vào `dependencies`; dev: không thêm gì)
- Create: `backend/app/worker/steps.py`, `backend/app/worker/case_runner.py`
- Test: `backend/tests/worker/site.py` (trang web giả), `backend/tests/worker/conftest.py`, `backend/tests/worker/test_steps.py`, `backend/tests/worker/test_case_runner.py`

**Interfaces:**
- Consumes: `AutoStep`, `AutoType`, `TargetBy`, `TestCase` (Task 1); `ProjectWorkerConfig` (Task 3); `ResultStatus` (Task 2).
- Produces:
  - `steps.py`: `class StepFailed(Exception)` (thông điệp tiếng Việt, ví dụ `Không thấy "Đăng nhập" trên trang`); `run_step(page: Page, step: AutoStep, base_url: str, *, timeout_ms: int) -> None`. Quy tắc: `goto` mở `base_url + value` (value bắt đầu bằng `http` thì dùng nguyên); `fill`/`click`/`select` tìm phần tử theo `target.by` (`text` → `get_by_text`, `label` → `get_by_label`, `css` → `locator`); `select` chọn theo nhãn hiển thị; `see_text` chờ chữ **hiện**; `not_see_text` chờ chữ **không hiện** (không có phần tử cũng coi là đạt); `url_is` so URL hiện tại với `base_url + value` (hoặc URL đầy đủ), bỏ dấu `/` cuối khi so.
  - `case_runner.py`: `blocked_reason(case: TestCase) -> str | None` (không bước nào có `auto` → `"Chưa có bước tự động"`; có bước thiếu → `"Bước 2 chưa có phần tự động"`, nêu số bước đầu tiên thiếu); `CaseOutcome(status: ResultStatus, reason: str, failed_step: int | None, screenshot: Path | None)` (dataclass); `class LoginError(Exception)`; `perform_login(browser: Browser, config: ProjectWorkerConfig, *, step_timeout_ms: int) -> dict[str, Any]` (chạy `login_steps`, thay `{email}`/`{password}`, trả `storage_state`; lỗi → `LoginError` **không chứa mật khẩu**); `class CaseSession` với `__init__(browser, storage_state, base_url, artifacts_dir: Path, run_id: str, *, step_timeout_ms, case_timeout_seconds)` và `run(case: TestCase) -> CaseOutcome`.
  - `CaseSession.run`: `blocked_reason` có giá trị → `BLOCKED` (không mở trình duyệt). Ngược lại mở context mới từ `storage_state`, chạy các bước theo thứ tự; xong hết → `PASS`; `StepFailed` → `FAIL` với `failed_step` (đánh số từ 1), `reason` = thông điệp lỗi, và chụp ảnh vào `artifacts_dir/<run_id>/<case.id>.png`; quá `case_timeout_seconds` hoặc lỗi bất ngờ của Playwright/worker (trình duyệt sập) → `INCONCLUSIVE`. Context luôn được đóng.

- [ ] **Step 1: Dựng trang giả** `tests/worker/site.py`: server `http.server` trong luồng nền, vài trang HTML nhỏ: `/login` (ô nhãn "Email", "Mật khẩu", nút "Đăng nhập" chuyển sang `/home`), `/home` (chữ "Xin chào" chỉ hiện khi đã đăng nhập bằng cookie), `/form` (ô nhập, `<select>` có "Hà Nội"/"Đà Nẵng", nút "Gửi" làm hiện chữ "Đã gửi"). Fixture `site` (trả `base_url`) và `browser` (Chromium headless; **skip** kèm lý do `chạy "uv run playwright install chromium"` nếu không mở được).
- [ ] **Step 2: Test bước** (`test_steps.py`, mỗi loại một test thành công + một test thất bại có thông điệp đúng): `goto`, `fill` (theo label), `click` (theo text), `select`, `see_text`, `not_see_text`, `url_is`, và `css` qua `by=css`; thêm `test_step_times_out_with_vietnamese_message` (`timeout_ms=500`).
- [ ] **Step 3: Test case** (`test_case_runner.py`):
  - `test_blocked_when_no_step_has_auto` và `test_blocked_names_first_step_missing_auto` (bước 1 có `auto`, bước 2 thiếu → `BLOCKED`, `reason` chứa "Bước 2", **không** mở trình duyệt: dùng `browser` giả ném lỗi nếu bị gọi)
  - `test_pass_when_all_steps_pass`, `test_fail_reports_step_number_and_screenshot` (file PNG tồn tại, đúng đường dẫn), `test_case_timeout_is_inconclusive`
  - `test_cases_do_not_share_state` (case A điền ô rồi kết thúc, case B mở lại trang thấy ô trống) và `test_login_session_is_reused` (case thấy "Xin chào" mà không đăng nhập lại)
  - `test_login_failure_raises_login_error_without_password`
- [ ] **Step 4: Chạy** → FAIL. **Step 5: Cài** `steps.py`, `case_runner.py`; chạy `uv sync` và `uv run playwright install chromium`.
- [ ] **Step 6: Chạy** `uv run pytest tests/worker -v`, `uv run pytest -q`, `uv run mypy app` (thêm `playwright.*` vào `ignore_missing_imports` nếu mypy đòi), `uv run ruff check` → sạch.
- [ ] **Step 7: Commit** `feat(worker): chạy bước tự động và từng test case bằng Playwright`

---

### Task 5: Chạy cả run, ghi lô, huỷ, khôi phục, tiến trình worker

**Files:**
- Create: `backend/app/worker/run_executor.py`, `backend/app/worker/__main__.py`
- Test: `backend/tests/worker/test_run_executor.py`

**Interfaces:**
- Consumes: `RunQueue`, `RunJob`, `RunRepository`, `ResultRepository`, `Run`, `Result`, `RunStatus`, `ResultStatus` (Task 2); `ProjectWorkerConfig`, `load_project_config`, `WorkerConfigError` (Task 3); `CaseOutcome`, `LoginError` (Task 4); `scope_for` (đã có `runs`/`results` từ Task 2); `Services`, `build_gateway`, `build_services`.
- Produces:
  - `class CaseSessionLike(Protocol)`: `run(case: TestCase) -> CaseOutcome`.
  - `SessionOpener = Callable[[Project, ProjectWorkerConfig, str], AbstractContextManager[CaseSessionLike]]` (nhận `project`, cấu hình, `run_id`; khối `with` lo bật app → mở trình duyệt → đăng nhập, thoát thì dọn hết; ném `AppStartError`/`LoginError`).
  - `class RunExecutor`: `__init__(services: Services, settings: Settings, queue: RunQueue, open_session: SessionOpener, *, clock: Callable[[], float] = time.monotonic, flush_every_cases: int = 10, flush_every_seconds: float = 30.0)`; `execute(job: RunJob) -> None`; `recover_interrupted_runs() -> int` (số run đã sửa).
  - `real_session_opener(settings: Settings) -> SessionOpener` (ghép `running_app` + Playwright + `perform_login` + `CaseSession`).
  - `__main__.py`: `python -m app.worker` — dựng services như `main.start_real_services`, gọi `recover_interrupted_runs()`, rồi vòng lặp `queue.pop(timeout_seconds=5)` → `execute`; bắt `KeyboardInterrupt` để thoát gọn; mọi ngoại lệ của một job được log (có `run_id`) và không làm worker chết.

Hành vi `execute(job)` (mỗi điểm có test ở Step 1):
1. `runs.claim(run_id)` trả `None` (đã huỷ, hoặc đã chạy) → bỏ qua, không làm gì.
2. Đọc lại các case theo `job.case_ids`, **chỉ giữ case còn `APPROVED`** (case bị đổi/xoá giữa chừng thì bỏ, không tính vào kết quả); cập nhật `run.total` theo số thực chạy.
3. `load_project_config` / `open_session` lỗi (`WorkerConfigError`, `AppStartError`, `LoginError`) → run `FAILED`, `queue.set_note(run_id, <lý do>)`, `finished_at`; **không** ghi kết quả nào.
4. Với mỗi case: trước khi chạy kiểm `queue.is_cancelled`; có cờ → thoát vòng lặp. `session.run(case)` ném lỗi bất ngờ → kết quả `INCONCLUSIVE` với lý do ngắn, vòng lặp tiếp tục.
5. Gom `Result` (mã `f"{run_id}-{case.id}"`, `screenshot` là đường dẫn tương đối `<run_id>/<case.id>.png` hoặc `None`); ghi lô khi đủ `flush_every_cases` hoặc quá `flush_every_seconds` (đo bằng `clock`), mỗi lần ghi cũng `runs.save` với `passed`/`failed` mới. Hết vòng lặp ghi nốt phần còn lại.
6. Kết thúc: có cờ huỷ → `CANCELLED`; ngược lại `COMPLETED`; `finished_at` luôn được đặt. `passed` = số `PASS`, `failed` = số `FAIL`.
7. Mọi ngoại lệ không lường trước trong `execute` → run `FAILED` kèm note `Lỗi không mong đợi: <loại lỗi>` (không kèm dữ liệu nhạy cảm), và vẫn thoát khối `open_session` (app được tắt).

`recover_interrupted_runs`: duyệt dự án chưa lưu trữ, run đang `RUNNING` → `FAILED`, note `Worker bị dừng giữa chừng`, `finished_at` đặt. Run `QUEUED` giữ nguyên (job vẫn nằm trong Redis nhờ AOF).

- [ ] **Step 1: Viết test** (`test_run_executor.py`; Sheet/Redis giả như `conftest`, `open_session` giả trả `CaseOutcome` theo từng case, ghi lại thứ tự gọi và việc đã đóng chưa):
  - `test_execute_marks_running_then_completed_and_counts_results`
  - `test_results_are_written_in_batches` (25 case, lô 10 → đúng 3 lời gọi `append:Results`; kiểm `gateway.calls`)
  - `test_time_based_flush` (đồng hồ giả nhảy 31 giây sau 2 case → ghi sớm)
  - `test_missing_auto_case_is_blocked_result_and_run_still_completes`
  - `test_cancel_between_cases_stops_and_keeps_written_results` (đặt cờ huỷ sau case 3; kết quả case 1–3 đã ghi, run `CANCELLED`, session đã đóng)
  - `test_cancelled_queued_run_is_skipped` (`cancel_if_queued` trước khi worker nhận)
  - `test_app_start_error_fails_run_with_note_and_no_results`; `test_login_error_fails_run`; `test_missing_project_config_fails_run_with_note`
  - `test_unexpected_case_exception_becomes_inconclusive_and_continues`
  - `test_case_no_longer_approved_is_skipped`
  - `test_unexpected_executor_error_fails_run_and_closes_session`
  - `test_recover_marks_running_runs_failed_and_keeps_queued`
- [ ] **Step 2: Chạy** → FAIL. **Step 3: Cài** `run_executor.py`, `__main__.py` theo hành vi trên.
- [ ] **Step 4: Chạy** `uv run pytest -q`, `uv run mypy app`, `uv run ruff check` → sạch. Thử tay: `uv run python -m app.worker` khởi động được và dừng bằng Ctrl+C khi chưa có job.
- [ ] **Step 5: Commit** `feat(worker): chạy cả run, ghi kết quả theo lô, huỷ và khôi phục run bị gián đoạn`

---

### Task 6: `RunService` và API `/runs`

**Files:**
- Create: `backend/app/core/services/runs.py`, `backend/app/api/routers/runs.py`
- Modify: `backend/app/main.py` (`include_router(runs.router)`). (`ProjectScope.runs/results` và `Services.max_cases_per_run/artifacts_dir` đã thêm ở Task 2.)
- Test: `backend/tests/test_run_service.py`, `backend/tests/test_runs_api.py`

**Interfaces:**
- Consumes: Task 2 (kho, hàng đợi), `TestCaseRepository.list_all`, `load_project`, `require`/`Action`, `CurrentUser`, `ServicesDep`.
- Produces:
  - `class NoCasesError(Exception)`, `class TooManyCasesError(Exception)` (cả hai mang thông điệp tiếng Việt).
  - `RunService(project: Project, test_cases: TestCaseRepository, runs: RunRepository, queue: RunQueue, *, max_cases: int)`: `select_cases(scope: RunScope) -> list[TestCase]` (chỉ `APPROVED`; lọc theo `screen_ids`, `priorities`, `severities` khi danh sách không rỗng; sắp theo `id`), `count(scope) -> int`, `start(triggered_by: str, scope: RunScope) -> Run` (rỗng → `NoCasesError`; quá `max_cases` → `TooManyCasesError`; `RunInProgressError` truyền thẳng; tạo run `QUEUED` với `branch=project.branch` rồi `queue.push(RunJob)`), `cancel(run_id: str, queue) -> Run` (`cancel_if_queued` thành công → trả run đã huỷ; run đang `RUNNING` → `queue.request_cancel`; run đã kết thúc → giữ nguyên, trả về như cũ; không có run → `RunNotFoundError`).
  - Router `prefix="/api/projects/{project_id}/runs"`:
    - `POST /preview` body `RunScope` → `{"count": int}` (`TRIGGER_RUN`, vì chỉ người chạy mới cần số này)
    - `POST ""` body `{"scope": RunScope}` → `201` `RunView`; 409 `Dự án đang có một lần chạy chưa xong`; 422 `Không có test case đã duyệt trong phạm vi này` / `Phạm vi có <n> case, vượt giới hạn <max> case mỗi lần chạy`
    - `GET ""` → `list[RunView]` (`VIEW_PROJECT`)
    - `GET /{run_id}` → `RunDetail` = `RunView` + `results: list[ResultView]` (`VIEW_PROJECT`); 404 `Không tìm thấy lần chạy`
    - `POST /{run_id}/cancel` → `RunView` (`TRIGGER_RUN`)
    - `GET /{run_id}/screenshots/{filename}` → `FileResponse` (`VIEW_PROJECT`)
    - `RunView` = `Run` + `note: str` (từ `queue.get_note`) + `triggered_by_name`; `ResultView` = `Result` + `test_case_title: str` (tra từ danh sách case, không có thì rỗng).
  - Ảnh: `filename` phải khớp `^[A-Za-z0-9._-]+\.png$`; run phải thuộc dự án (có trong `Runs` của dự án), file nằm trong `artifacts_dir/<run_id>/` (kiểm bằng `Path.resolve()` còn nằm trong thư mục đó); không thoả → 404.

- [ ] **Step 1: Test service** (`test_run_service.py`): `test_only_approved_cases_are_selected`, `test_scope_filters_by_screen_priority_severity`, `test_empty_scope_result_raises_no_cases`, `test_too_many_cases_raises`, `test_start_creates_queued_run_and_pushes_job_with_case_ids`, `test_start_while_active_raises_in_progress_and_pushes_nothing`, `test_cancel_queued_run_is_cancelled_directly`, `test_cancel_running_run_sets_flag`, `test_cancel_finished_run_is_noop`.
- [ ] **Step 2: Test API** (`test_runs_api.py`, theo mẫu `test_test_cases_api.py` với `client_for`): `test_tester_cannot_start_run` (403), `test_viewer_can_list_runs_but_not_start`, `test_start_run_returns_201_and_job_in_queue`, `test_second_start_returns_409`, `test_preview_returns_count`, `test_other_project_member_gets_404`, `test_get_run_includes_results_with_titles`, `test_cancel_returns_updated_run`, `test_screenshot_served_for_own_run`, `test_screenshot_rejects_path_traversal` (`..%2f`, `/`, đuôi không phải `.png`), `test_screenshot_of_run_in_other_project_is_404`.
- [ ] **Step 3: Chạy** → FAIL. **Step 4: Cài** theo Interfaces.
- [ ] **Step 5: Chạy** `uv run pytest -q`, `uv run mypy app`, `uv run ruff check` → sạch.
- [ ] **Step 6: Commit** `feat(api): tạo, xem và huỷ lần chạy test; xem ảnh chụp lỗi`

---

### Task 7: Sinh lại kiểu API và xin chủ dự án mô tả chỗ form bị vỡ

**Files:**
- Modify: `frontend/lib/api/openapi.json`, `frontend/lib/api/schema.d.ts`, `frontend/lib/api/types.ts`

**Interfaces:**
- Produces trong `types.ts`: `AutoStep`, `AutoTarget`, `AutoType`, `TargetBy`, `Run`, `RunDetail`, `RunView`, `ResultView`, `RunScope`, `RunStatus`, `ResultStatus` (đều là `Schemas["..."]`).

- [ ] **Step 1: Chạy** `cd frontend && npm run gen:api` rồi thêm các `export type` trên vào `types.ts`.
- [ ] **Step 2: Chạy** `npm run typecheck` và `npm test` → sạch (58 test cũ qua).
- [ ] **Step 3: Cổng chặn — dừng và hỏi chủ dự án trước khi làm Task 8**: chủ dự án báo form tạo/sửa case đang "vỡ" ở vài chỗ nhưng chưa nói cụ thể. Xin **ảnh chụp hoặc mô tả** từng chỗ (ô tràn khung, nút bị che, chữ bị cắt, lệch trên màn hình nhỏ...). Sửa các chỗ đó thành một commit riêng `fix(frontend): sửa lỗi hiển thị form test case` (kèm test nếu sửa logic) **trước** khi thêm phần "Tự động". Nếu chủ dự án nói không cần sửa thì bỏ qua và ghi vào kết quả báo cáo.
- [ ] **Step 4: Commit** `chore(frontend): sinh lại kiểu API cho bước tự động và lần chạy`

---

### Task 8: Phần "Tự động" trong form bước

**Files:**
- Modify: `frontend/lib/test-cases/steps.ts`, `frontend/lib/test-cases/form-schema.ts`, `frontend/components/test-cases/steps-editor.tsx`, `frontend/components/test-cases/case-read-only.tsx`, `frontend/messages/vi.json`
- Create: `frontend/components/test-cases/auto-step-fields.tsx`
- Test: `frontend/lib/test-cases/steps.test.ts`, `frontend/lib/test-cases/form-schema.test.ts` (đã có hoặc tạo mới), `frontend/components/test-cases/steps-editor.test.tsx`

**Interfaces:**
- Consumes: kiểu `AutoStep`, `AutoType`, `TargetBy` (Task 7); `StepsEditor` props hiện có (`steps`, `onChange`, `errors`, `disabled`).
- Produces trong `steps.ts`: `AUTO_TYPES: AutoType[]` (đúng thứ tự `goto, fill, click, select, see_text, not_see_text, url_is`); `autoNeedsTarget(type: AutoType): boolean` (`fill`/`click`/`select`); `autoNeedsValue(type: AutoType): boolean` (mọi loại trừ `click`; `fill` được để trống nhưng vẫn hiện ô nhập); `defaultAuto(type: AutoType): AutoStep` (có `target` `{by:"label"|"text", value:""}` khi cần: `fill`/`select` mặc định `by:"label"`, `click` mặc định `by:"text"`); `isAutoComplete(auto: AutoStep): boolean`.
- `auto-step-fields.tsx`: `AutoStepFields({ value: AutoStep | undefined, onChange(next: AutoStep | undefined), disabled?, error? })`.

- [ ] **Step 1: Test hàm thuần** (`steps.test.ts`): `defaultAuto` cho từng loại (có/không `target` đúng quy tắc), `autoNeedsTarget`/`autoNeedsValue`, `isAutoComplete` (click thiếu `target.value` → false; `goto` value rỗng → false; `fill` value rỗng + có target → true), `insertStepAfter` vẫn tạo bước trống không có `auto`.
- [ ] **Step 2: Test schema** (`form-schema.test.ts`): case cũ không có `auto` qua được; `auto` sai (loại cần target mà thiếu) bị báo lỗi theo khoá `testCases.form.errors.*` (thêm khoá mới trong `vi.json`); `auto` hợp lệ giữ nguyên khi submit.
- [ ] **Step 3: Test component** (`steps-editor.test.tsx`): phần "Tự động" **thu gọn mặc định** (dùng `<details>`); mở ra chọn loại → các ô hiện đúng theo loại; mục "Nâng cao" ẩn lựa chọn `css` cho tới khi mở; chọn "Không dùng tự động" gọi `onChange` với `auto` bị bỏ khỏi bước; `disabled` thì không sửa được.
- [ ] **Step 4: Chạy** `npm test` → FAIL.
- [ ] **Step 5: Cài** hàm thuần, `AutoStepFields` (chọn loại bằng `enum-select.tsx` hiện có; ô "Tìm theo" chữ hiển thị/label; ô giá trị; "Nâng cao" chứa lựa chọn CSS), gắn vào `steps-editor.tsx` dưới ô "kết quả mong đợi" của từng bước; `case-read-only.tsx` hiện tóm tắt một dòng khi bước có `auto` (ví dụ `Nhập "qa@x.com" vào ô "Email"`). Mọi chuỗi mới nằm trong `vi.json` nhóm `testCases.auto`. Trường `auto` rỗng thì **không đưa vào** payload gửi lên.
- [ ] **Step 6: Chạy** `npm test`, `npm run typecheck`, `npm run lint` → sạch. Mở form trên máy bằng `npm run dev` và kiểm bằng mắt: thu gọn/mở, thêm/xoá/kéo bước vẫn đúng; không vỡ bố cục ở độ rộng điện thoại (≈ 375px).
- [ ] **Step 7: Commit** `feat(frontend): thêm phần Tự động vào từng bước của test case`

---

### Task 9: Tab "Chạy test"

**Files:**
- Create: `frontend/lib/use-runs.ts`, `frontend/components/runs/run-launcher.tsx`, `frontend/components/runs/run-list.tsx`, `frontend/components/runs/run-detail.tsx`, `frontend/app/(app)/projects/[projectId]/runs/page.tsx`
- Modify: `frontend/lib/project-tabs.ts`, `frontend/messages/vi.json`
- Test: `frontend/lib/use-runs.test.tsx`, `frontend/lib/project-tabs.test.ts`, `frontend/components/runs/run-detail.test.tsx`

**Interfaces:**
- Consumes: kiểu từ Task 7; API Task 6; cách gọi API của `lib/use-test-cases.ts` (`openapi-fetch` client + TanStack Query) và `use-project-id.ts`, `use-project-data.ts` cho quyền.
- Produces: `useRuns(projectId)`, `useRun(projectId, runId)` (**tự làm mới mỗi 3 giây khi run còn `QUEUED`/`RUNNING`**, dừng khi xong), `usePreviewRun`, `useStartRun`, `useCancelRun`; `{ segment: "runs", labelKey: "runs", permission: "VIEW_PROJECT" }` trong `PROJECT_TABS` (sau `test-cases`).

- [ ] **Step 1: Test** `project-tabs.test.ts` (tab `runs` hiện với mọi role xem được dự án); `use-runs.test.tsx` (`useRun` bật polling khi `RUNNING`, tắt khi `COMPLETED`); `run-detail.test.tsx`: hiện thống kê `PASS/FAIL/BLOCKED/INCONCLUSIVE` (màu như spec mục 11: xanh lá/đỏ/cam/xám), tiến độ "12/50", lọc theo status, mở một case FAIL thấy lý do + "Bước <n>" + ảnh chụp (`<img>` trỏ tới `/api/projects/<id>/runs/<run>/screenshots/<file>`), run `FAILED` hiện `note`.
- [ ] **Step 2: Chạy** → FAIL. **Step 3: Cài**:
  - `run-launcher.tsx`: chọn phạm vi (cả dự án hoặc chọn màn hình; lọc priority/severity), **hiện số case sẽ chạy** (gọi `/preview`), nút "Chạy" **chỉ hiện khi có quyền `TRIGGER_RUN`** và **khoá khi có run `QUEUED`/`RUNNING`** (kèm chữ giải thích), lỗi 409/422 hiện đúng câu của backend qua toast.
  - `run-list.tsx` (danh sách run, mới nhất trước, click vào để xem), `run-detail.tsx` (thống kê, tiến độ, nút "Huỷ" cho `TRIGGER_RUN` khi run chưa xong, danh sách kết quả).
  - Chuỗi mới nằm trong `vi.json` nhóm `runs`.
- [ ] **Step 4: Chạy** `npm test`, `npm run typecheck`, `npm run lint` → sạch.
- [ ] **Step 5: Commit** `feat(frontend): thêm tab Chạy test với tiến độ, kết quả và ảnh chụp lỗi`

---

### Task 10: Chạy thử đầu cuối, tài liệu và quyết định

**Files:**
- Modify: `DECISIONS.md`, `README.md`
- Create: `worker-projects.example.json` (mẫu, không có mật khẩu thật)

- [ ] **Step 1: Chạy thử đầu cuối với app thật** khi chủ dự án đã gửi đường dẫn repo, lệnh chạy, URL và tài khoản test (nếu chưa có thì dừng ở bước này và báo lại, các task trước vẫn hoàn tất): tạo `worker-projects.json` thật (gitignore), `docker compose up redis api frontend`, `uv run python -m app.worker`, tạo một case `APPROVED` có bước tự động, bấm "Chạy" trên web, kiểm: PASS khi đúng, FAIL kèm ảnh khi cố ý sai, BLOCKED khi thiếu bước, huỷ giữa chừng, tắt worker giữa run rồi mở lại (run bị `FAILED` đúng lý do). Ghi kết quả thật, kể cả phần không chạy được.
- [ ] **Step 2: README**: thêm mục "Chạy worker" (cài `uv run playwright install chromium`; tạo `worker-projects.json` từ file mẫu; chạy `uv run python -m app.worker` ở máy có app; lưu ý worker **không** chạy trong Docker; Redis dùng cổng `127.0.0.1:6379`).
- [ ] **Step 3: `DECISIONS.md`**: thêm 5 mục **[Quyết định M4]** (đã liệt kê ở đầu kế hoạch).
- [ ] **Step 4: Chạy toàn bộ** `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check`, `cd frontend && npm test && npm run typecheck && npm run lint` → ghi số test thực tế.
- [ ] **Step 5: Commit** `docs: hướng dẫn chạy worker và ghi quyết định M4`
- [ ] **Step 6: Ghi chú học** bằng skill `writing-learning-notes` (file `learning-notes/10-...html`, **không commit**) và cập nhật `project-status.md` trong memory. Không push, không tạo PR; hỏi chủ dự án.

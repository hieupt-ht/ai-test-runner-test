# Giao diện vui hơn: Kẹo ngọt, đồ thị, nhím bug, xếp hạng, nhạc — kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm giao diện thứ 3 "Kẹo ngọt", đồ thị ở Tổng quan chung và Tổng quan project, con nhím riêng của từng người (lớn theo bug, biểu cảm theo chuỗi ngày), bảng xếp hạng theo project và nút nhạc lofi.

**Architecture:** Backend gom dữ liệu gốc của mỗi project thành một "bản tóm tắt" `ProjectFacts` (case + kết quả rút gọn), lưu Redis bằng `GenerationCache` (TTL 10 phút, xoá ngay khi ghi case/kết quả). Mọi con số (thẻ số, đồ thị, xếp hạng, nhím, chuỗi) là **hàm thuần** trong `app/core/services/stats.py`, nhận `ProjectFacts` + `today` nên không phụ thuộc giờ cache. Frontend thêm lớp `.candy` gồm đủ biến màu, đồ thị Recharts tải động, nhím là SVG thuần, nhạc là một thẻ `<audio>` dùng chung ở layout `(app)`.

**Tech Stack:** FastAPI, Pydantic, Redis (`GenerationCache`), pytest + FakeSheetsGateway + fakeredis; Next.js 16, Tailwind 4, next-themes, TanStack Query, next-intl, Recharts, vitest.

**Spec:** `docs/superpowers/specs/2026-11-19-giao-dien-vui-nhim-bug-design.md`

## Tiến độ

- [x] Đợt 1: giao diện Kẹo ngọt (Task 1–2)
- [ ] Đợt 2: backend số liệu + API + cache (Task 3–8)
- [ ] Đợt 3: Tổng quan project + đồ thị Tổng quan chung (Task 9–11)
- [ ] Đợt 4: nhím + chuỗi ngày (Task 12–13)
- [ ] Đợt 5: bảng xếp hạng (Task 14)
- [ ] Đợt 6: nút nhạc (Task 15–16)

Làm **một đợt mỗi lần**: xong đợt thì đánh dấu ở đây, ghi một đoạn ngắn vào `HANDOFF.md` (mục "Đang làm (2026-11-19): giao diện vui + nhím bug"), báo chủ dự án rồi dừng.

## Global Constraints

- Làm trong worktree `D:/workspace/TTNGOAI/ai-test-runner-fun-ui`, nhánh `feature/fun-ui` (tách từ `feature/ai-agent-runner` @ 4925372). Không đụng thư mục `ai-test-runner` gốc: tab Claude khác đang làm ở đó.
- Không push, không tạo PR khi chưa được đồng ý. Không commit thẳng vào `main`.
- Commit Conventional Commits, type tiếng Anh, nội dung tiếng Việt có dấu, viết bằng heredoc Git Bash, kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Chỉ `git add` đúng file của task.
- TDD: viết test, xem đỏ, rồi mới code. Comment tiếng Việt, code dễ đọc cho sinh viên.
- Không in hay commit giá trị trong `.env` và `worker-projects.json`.
- Frontend Next.js 16: đọc guide liên quan trong `frontend/node_modules/next/dist/docs/` trước khi viết route mới hoặc dùng `next/dynamic`.
- Component mới **chỉ dùng biến màu** (`bg-card`, `text-muted-foreground`, `var(--chart-1)`, `var(--chart-pass)`…). Ngoại lệ duy nhất: thân con nhím (tím `#B58CFF`→`#5B3A8C`, mặt `#FFFFFF`→`#FFE3F1`, viền gai `#7B55B8`, tai `#FFC2D9`, má `#FF8FC0`, mắt `#22163A`).
- Giờ Việt Nam cho mọi "ngày": `moment.astimezone(VIETNAM).date()` (`app.core.time.VIETNAM`); "hôm nay" = `today_in_vietnam()`.
- So email luôn qua `normalize_email` (`app.core.models.user`).
- Nhạc không bao giờ tự phát; `<audio preload="none">`.
- Mỗi task xong chạy: `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check app tests`; task frontend thêm `cd frontend && npx vitest run && npx tsc --noEmit && npx eslint .`. Chỉ `ruff format` file mình sửa.

## Review Focus

1. **Kết quả trỏ tới case đã bị xoá / không có trong danh sách** (agent gửi muộn): bỏ qua khi tính bug, % Pass, bug mở; không lỗi 500. → test trong Task 3 và Task 5.
2. **Email khác hoa/thường** (`An@X.com` ở `executed_by`, `an@x.com` ở `created_by`/user): là cùng một người ở bug, ngày làm việc, xếp hạng. → test Task 3, Task 4.
3. **Một project có Sheet hỏng** (mất quyền, thiếu cột) trong `/me/pet` và `/me/dashboard`: bỏ qua project đó, vẫn trả 200 với các project còn lại (giống `my_overview`). → test Task 8.
4. **Kết quả lúc 23:30 UTC** thuộc **ngày hôm sau** theo giờ Việt Nam (đồ thị ngày, lọc tuần, "hôm nay bắt được bug"). → test Task 3, Task 5.
5. **Project trống** (chưa có case/kết quả): thẻ số = 0, `pass_rate = null`, đồ thị hiện "Chưa có dữ liệu", không vỡ trang. → test Task 5, Task 10.

---

## Đợt 1 — Giao diện "Kẹo ngọt"

### Task 1: Biến màu `.candy` + màu ngữ nghĩa cho đồ thị

**Files:**
- Modify: `frontend/app/globals.css`
- Test: `frontend/app/globals-css.test.ts` (mới)

**Interfaces:**
- Produces: lớp CSS `.candy` trên `<html>`; biến mới có ở cả `:root`, `.dark`, `.candy`: `--chart-pass`, `--chart-fail`, `--chart-other`, kèm `--color-chart-pass|fail|other` trong `@theme inline` (dùng được `bg-chart-pass`, `text-chart-fail`…).

- [ ] **Step 0: Chuẩn bị worktree** — `cd frontend && npm ci`; `cd backend && uv sync`. Chạy cả hai bộ test một lần để chắc nền xanh (ghi số test vào ghi chú đợt).

- [ ] **Step 1: Viết test đỏ** `globals-css.test.ts` (đọc file bằng `readFileSync`, tách từng khối `:root {…}`, `.dark {…}`, `.candy {…}` bằng regex, lấy tập tên biến `--xxx`):
  - `it("Kẹo ngọt khai báo đủ mọi biến màu như giao diện Sáng")`: `vars(".candy")` ⊇ `vars(":root")`.
  - `it("cả ba giao diện đều có màu Pass/Fail/Khác cho đồ thị")`: mỗi khối có `--chart-pass`, `--chart-fail`, `--chart-other`.
  - `it("Kẹo ngọt dùng đúng bảng màu đã chốt")`: `.candy` có `--background: #FFF7FB`, `--card: #FFFFFF`, `--foreground: #3A2350`, `--primary: #B15CFF`, `--chart-1: #C4A1FF`, `--chart-2: #FF9FCB`, `--chart-3: #8BE3C9`, `--border: #F3DDF0`, `--sidebar: #FBE9F7`.

- [ ] **Step 2:** `npx vitest run app/globals-css.test.ts` → FAIL (không có khối `.candy`).

- [ ] **Step 3: Thêm vào `globals.css`.** Không đổi bất kỳ giá trị nào đang có của `:root`/`.dark` (chỉ thêm 3 biến mới vào cuối mỗi khối).
  - `:root`: `--chart-pass: oklch(0.63 0.17 149)`, `--chart-fail: oklch(0.58 0.22 27)`, `--chart-other: oklch(0.71 0.01 286)`.
  - `.dark`: `--chart-pass: oklch(0.79 0.18 152)`, `--chart-fail: oklch(0.71 0.17 22)`, `--chart-other: oklch(0.55 0.01 286)`.
  - `.candy` (giá trị ngoài bảng ở spec mục 5 là quyết định của người viết plan):
    `--background #FFF7FB; --foreground #3A2350; --card #FFFFFF; --card-foreground #3A2350; --popover #FFFFFF; --popover-foreground #3A2350; --primary #B15CFF; --primary-foreground #FFFFFF; --secondary #F6E8FF; --secondary-foreground #3A2350; --muted #FBEFF7; --muted-foreground #85679B; --accent #FBE3F4; --accent-foreground #3A2350; --destructive #E5487A; --border #F3DDF0; --input #EBCDE6; --ring #C9A0FF; --chart-1 #C4A1FF; --chart-2 #FF9FCB; --chart-3 #8BE3C9; --chart-4 #FFD08A; --chart-5 #8FC8FF; --chart-pass #3FBF97; --chart-fail #FF6FA8; --chart-other #C9B8D6; --radius 0.875rem; --sidebar #FBE9F7; --sidebar-foreground #3A2350; --sidebar-primary #B15CFF; --sidebar-primary-foreground #FFFFFF; --sidebar-accent #F6D9EF; --sidebar-accent-foreground #3A2350; --sidebar-border #F3DDF0; --sidebar-ring #C9A0FF;`
  - `--muted-foreground` đậm hơn mẫu `#9C7FB0` một chút để chữ nhỏ trên nền trắng đạt tương phản 4.5:1 (ghi comment lý do).
  - `@theme inline`: thêm `--color-chart-pass/fail/other: var(--chart-…)`.
  - Không thêm `.candy` vào `@custom-variant dark`: Kẹo ngọt là giao diện sáng, các badge dùng `dark:` sẽ hiện màu bản sáng (đúng ý).

- [ ] **Step 4:** `npx vitest run app/globals-css.test.ts` → PASS.

- [ ] **Step 5: Commit** `feat(frontend): thêm bảng màu Kẹo ngọt và màu Pass/Fail cho đồ thị`.

### Task 2: Chọn "Kẹo ngọt" trong menu + rà màn hình

**Files:**
- Modify: `frontend/app/providers.tsx`, `frontend/components/app-shell/topbar.tsx`, `frontend/messages/vi.json` (`topbar.themeCandy: "Kẹo ngọt"`)
- Test: `frontend/components/app-shell/topbar.test.tsx`

**Interfaces:**
- Consumes: lớp `.candy` (Task 1).
- Produces: `setTheme("candy")`; `useTheme().resolvedTheme` có thể là `"candy"`.

- [ ] **Step 1: Test đỏ** trong `topbar.test.tsx`: `it("menu Giao diện có mục Kẹo ngọt và bấm thì đổi sang candy")`. Đổi mock `next-themes` thành `const setTheme = vi.fn()` dùng chung (vi.hoisted); mở menu người dùng, bấm `menuitem` "Kẹo ngọt" → `expect(setTheme).toHaveBeenCalledWith("candy")`.
- [ ] **Step 2:** `npx vitest run components/app-shell/topbar.test.tsx` → FAIL.
- [ ] **Step 3:** `ThemeProvider` thêm `themes={["light", "dark", "candy"]}` (giữ `defaultTheme="system" enableSystem`). Topbar thêm `DropdownMenuItem` "Kẹo ngọt" (icon `Candy` của lucide) giữa Tối và Theo hệ thống.
- [ ] **Step 4:** Test PASS.
- [ ] **Step 5: Rà bằng trình duyệt.** `npm run dev` (backend chạy như HANDOFF hướng dẫn), bật Kẹo ngọt rồi lần lượt Sáng/Tối, mở: Tổng quan, Việc của tôi, Quản lý dự án, Người dùng, từng tab của một project (Màn hình, Test case, chi tiết case, Kết quả + bảng chi tiết, Chia việc, Thành viên, Cài đặt), hộp thoại đổi mật khẩu, chuông thông báo. Tìm: chữ chìm vào nền, viền mất, màu không đổi. Sửa chỗ hỏng bằng biến màu. Đã biết các chỗ cứng hiện có (`bg-black` khung video, `text-white` trên `bg-destructive`, badge `dark:`) đều ổn ở cả 3 giao diện — không cần sửa nếu nhìn thấy ổn.
- [ ] **Step 6: Commit** `feat(frontend): thêm giao diện Kẹo ngọt vào menu`. Cập nhật Tiến độ + HANDOFF, báo chủ dự án, **dừng đợt 1**.

---

## Đợt 2 — Backend: số liệu, cache, 4 API

Mọi model mới nằm trong `backend/app/core/models/stats.py`; mọi hàm thuần trong `backend/app/core/services/stats.py`; test thuần trong `backend/tests/test_stats.py` (dựng `ProjectFacts` bằng tay, không cần Sheets).

### Task 3: `ProjectFacts` và luật "bắt được 1 bug"

**Files:**
- Create: `backend/app/core/models/stats.py`, `backend/app/core/services/stats.py`
- Test: `backend/tests/test_stats.py`

**Interfaces:**
- Produces (models, đều là `BaseModel`):
  - `CaseFact(id: str, screen_id: str, status: TestCaseStatus, created_by: str, created_at: datetime)`
  - `ResultFact(case_id: str, status: ResultStatus, created_at: datetime, executed_by: str, case_version: int | None)`
  - `ProjectFacts(cases: list[CaseFact], results: list[ResultFact])`
  - `BugEvent(email: str, case_id: str, day: date)` (dataclass frozen cũng được)
- Produces (hàm):
  - `facts_from(cases: list[TestCase], results: list[Result]) -> ProjectFacts` — `created_by`, `executed_by` đã `normalize_email` nếu chứa "@".
  - `vn_day(moment: datetime) -> date`
  - `bug_events(facts: ProjectFacts) -> list[BugEvent]`

Luật `bug_events` (spec 6.5): gom kết quả **FAIL** theo `(case_id, case_version)` (`None` là một nhóm riêng của case đó); mỗi nhóm lấy FAIL có `created_at` sớm nhất; người được tính = `executed_by` nếu chứa "@", ngược lại = `created_by` của case; case không có trong `facts.cases` và kết quả là agent → bỏ qua; `day = vn_day(created_at)`.

- [ ] **Step 1: Test đỏ:**
  - `test_fail_by_person_credits_runner`: FAIL `executed_by="Lan@X.com"` → `[BugEvent("lan@x.com", "TC-1", …)]`.
  - `test_fail_by_agent_credits_case_author`: `executed_by="codex-windows"`, case `created_by="minh@x.com"` → email `minh@x.com`.
  - `test_many_fails_same_version_count_once_for_first_fail`: 3 FAIL v2 (lan 09:00, minh 10:00, lan 11:00) + 1 PASS xen giữa → đúng 1 event, email `lan@x.com`, day ngày 09:00.
  - `test_new_version_fail_counts_again`: FAIL v1 + FAIL v2 → 2 event.
  - `test_missing_version_is_one_group`: 2 FAIL `case_version=None` → 1 event.
  - `test_blocked_and_inconclusive_are_ignored`: chỉ BLOCKED/INCONCLUSIVE → `[]`.
  - `test_agent_fail_for_deleted_case_is_skipped`: case_id không có trong cases → `[]`.
  - `test_vietnam_day_boundary`: FAIL `2026-11-18T17:30:00Z` → `day == date(2026, 11, 19)`.
- [ ] **Step 2:** `uv run pytest tests/test_stats.py -q` → FAIL (import lỗi).
- [ ] **Step 3:** Viết models + `facts_from`, `vn_day`, `bug_events`.
- [ ] **Step 4:** Test PASS.
- [ ] **Step 5: Commit** `feat(backend): tính bug bắt được từ kết quả test`.

### Task 4: Ngày làm việc, chuỗi, biểu cảm, cấp nhím

**Files:**
- Modify: `backend/app/core/models/stats.py`, `backend/app/core/services/stats.py`
- Test: `backend/tests/test_stats.py`

**Interfaces:**
- Produces:
  - `class PetMood(StrEnum): HAPPY, NORMAL, HUNGRY, CRY` (giá trị = tên)
  - `MyPet(level: int, bugs: int, bugs_to_next: int | None, streak: int, missed_days: int, mood: PetMood)` — `level` 1..4.
  - `work_days(facts_list: list[ProjectFacts], email: str) -> set[date]` — ngày VN có case `created_by == email` hoặc kết quả `executed_by == email` (chỉ kết quả của người; kết quả agent không tính là ngày làm việc của tác giả case — quyết định của người viết plan).
  - `streak_and_missed(days: set[date], today: date) -> tuple[int, int]`
  - `level_for(bugs: int) -> tuple[int, int | None]` — mốc `[0, 5, 20, 50]`; trả `(cấp, số bug còn thiếu để lên cấp)`, cấp 4 → `None`.
  - `mood_for(*, caught_bug_today: bool, worked_today: bool, missed_days: int) -> PetMood`
  - `build_pet(facts_list: list[ProjectFacts], email: str, today: date) -> MyPet`

Thuật toán chuỗi (spec 6.3): đi lùi từng ngày từ `today`; ngày có làm → `streak += 1`; ngày không làm: nếu là `today` hoặc thứ 7/CN → đi tiếp, nếu là thứ 2–6 → dừng. Dừng khi đã lùi qua ngày làm việc sớm nhất. `missed` = số ngày thứ 2–6 nằm **giữa** ngày làm việc gần nhất và `today` (không tính cả hai); chưa từng làm → `(0, 0)`. Biểu cảm theo thứ tự: bắt bug hôm nay → HAPPY; làm hôm nay hoặc `missed == 0` → NORMAL; `missed` 1–2 → HUNGRY; ≥3 → CRY.

- [ ] **Step 1: Test đỏ** (`today` cố định, ví dụ thứ 2 `date(2026, 11, 23)`):
  - `test_friday_work_keeps_streak_on_monday_morning`: làm thứ 4,5,6 tuần trước, hôm nay thứ 2 chưa làm → `(3, 0)`.
  - `test_weekend_work_adds_to_streak`: làm thứ 6, thứ 7, thứ 2 (hôm nay) → `(3, 0)`.
  - `test_missing_one_weekday_breaks_streak`: làm thứ 4 tuần trước, không làm thứ 5, làm thứ 6 → `streak == 1`.
  - `test_missed_days_count_only_past_weekdays`: làm lần cuối thứ 3 tuần trước (17/11), hôm nay thứ 2 (23/11) → `missed == 3` (thứ 4, 5, 6).
  - `test_never_worked_is_zero`: `set()` → `(0, 0)`.
  - `test_level_thresholds`: `level_for(0) == (1, 5)`, `(4) == (1, 1)`, `(5) == (2, 15)`, `(19) == (2, 1)`, `(20) == (3, 30)`, `(50) == (4, None)`.
  - `test_mood_rules`: 4 trường hợp, mỗi biểu cảm một lần + `missed=0, worked_today=False` → NORMAL.
  - `test_work_days_match_email_ignoring_case`: case `created_by="an@x.com"`, kết quả `executed_by="AN@x.com"` → cả hai ngày có trong `work_days(…, "an@x.com")`.
  - `test_build_pet_sums_bugs_across_projects`: 2 `ProjectFacts`, mỗi cái 3 bug của An → `bugs == 6`, `level == 2`.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt các hàm trên.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(backend): tính chuỗi ngày, cấp và biểu cảm của nhím`.

### Task 5: Số liệu project, đồ thị ngày, xếp hạng

**Files:**
- Modify: `backend/app/core/models/stats.py`, `backend/app/core/services/stats.py`
- Test: `backend/tests/test_stats.py`

**Interfaces:**
- Produces (models):
  - `DayCount(day: date, passed: int, failed: int, other: int)`
  - `ScreenProgress(screen_id: str, screen_name: str, done: int, total: int)`
  - `ProjectStats(total_cases: int, pass_rate: float | None, open_bugs: int, daily: list[DayCount], case_status: dict[TestCaseStatus, int], screens: list[ScreenProgress])` — `case_status` luôn đủ 4 khoá DRAFT, IN_REVIEW, APPROVED, TESTED.
  - `class Period(StrEnum): WEEK="week", MONTH="month", ALL="all"`
  - `LeaderboardRow(rank: int | None, email: str, name: str, count: int)`
  - `Board(top: list[LeaderboardRow], me: LeaderboardRow | None)` — `me` chỉ có khi người xem ngoài top.
  - `Leaderboard(period: Period, cases: Board, bugs: Board)`
- Produces (hàm):
  - `daily_counts(facts_list: list[ProjectFacts], today: date, days: int = 14) -> list[DayCount]` — đủ `days` ngày liên tiếp kết thúc ở `today`, tăng dần, ngày trống = 0; đếm **mỗi dòng kết quả**; BLOCKED + INCONCLUSIVE vào `other`.
  - `progress(facts: ProjectFacts) -> tuple[int, int]` — `(done, total)`; total bỏ ARCHIVED/DEPRECATED, done = APPROVED hoặc TESTED.
  - `project_stats(facts: ProjectFacts, screen_names: dict[str, str], today: date) -> ProjectStats` — `screens` theo thứ tự `screen_names`, màn hình không có case vẫn hiện `0/0`.
  - `period_start(period: Period, today: date) -> date | None` — WEEK: thứ 2 tuần này; MONTH: ngày 1; ALL: `None`.
  - `leaderboard(facts: ProjectFacts, names: dict[str, str], period: Period, today: date, me: str, top: int = 5) -> Leaderboard`

Luật: "bug mở" và "% Pass" chỉ xét case chưa ARCHIVED/DEPRECATED, lấy kết quả PASS/FAIL **mới nhất** theo `created_at` của mỗi case (spec 6.5). Xếp hạng: người có `count > 0`, sắp `count` giảm rồi `name` tăng, hạng kiểu 1,1,3 khi bằng điểm; tên lấy từ `names`, thiếu thì dùng email; `me` không có điểm → `LeaderboardRow(rank=None, count=0)`. Bảng case: đếm case APPROVED/TESTED theo `created_by`, lọc `vn_day(created_at) >= start`. Bảng bug: `bug_events` lọc `day >= start`.

- [ ] **Step 1: Test đỏ:**
  - `test_empty_project_stats`: `ProjectFacts([], [])` → `total_cases 0`, `pass_rate is None`, `open_bugs 0`, `len(daily) == 14`, `case_status` đủ 4 khoá = 0.
  - `test_pass_rate_and_open_bugs_use_latest_pass_fail`: case A: FAIL rồi PASS; case B: PASS rồi FAIL rồi BLOCKED; case C chỉ BLOCKED; case D ARCHIVED có FAIL → `pass_rate == 0.5`, `open_bugs == 1`.
  - `test_results_of_unknown_case_are_ignored`: kết quả của `TC-X` không có trong cases → không ảnh hưởng `pass_rate`/`open_bugs`, nhưng **có** trong `daily` (đồ thị đếm mọi lần chạy — quyết định của người viết plan).
  - `test_daily_counts_buckets_by_vietnam_day`: PASS `…T17:30:00Z` ngày 18 → nằm ở ngày 19; BLOCKED + INCONCLUSIVE cùng ngày → `other == 2`.
  - `test_screen_progress_counts_done_over_total`: SC-1 có DRAFT, APPROVED, TESTED, DEPRECATED → `done 2, total 3`; SC-2 không case → `0/0`.
  - `test_period_start`: today thứ 5 `2026-11-19` → WEEK `2026-11-16`, MONTH `2026-11-01`, ALL `None`.
  - `test_leaderboard_cases_counts_approved_and_tested_by_author`: An 2 APPROVED + 1 DRAFT, Bình 1 TESTED → `cases.top == [(1, an, 2), (2, binh, 1)]`.
  - `test_leaderboard_ties_share_rank`: hai người cùng 3 bug → rank 1, 1; người sau rank 3.
  - `test_leaderboard_me_outside_top`: 6 người có bug, `me` hạng 6 → `bugs.me.rank == 6`; `me` không có bug → `rank None, count 0`; `me` trong top → `bugs.me is None`.
  - `test_leaderboard_week_filter`: bug ngày 15/11 (CN tuần trước) không vào WEEK của 19/11, có trong MONTH; bug ngày 16/11 (thứ 2) có trong WEEK.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(backend): số liệu project và bảng xếp hạng`.

### Task 6: Cache `ProjectFacts` + xoá cache khi ghi

**Files:**
- Create: `backend/app/core/stats_cache.py`
- Modify: `backend/app/core/repositories/test_cases.py`, `backend/app/core/repositories/runs.py`, `backend/app/api/project_scope.py`, `backend/app/api/services.py`, `backend/app/settings.py`
- Modify (sửa chỗ dựng `ResultRepository`): `backend/tests/test_run_repository.py`, `backend/tests/test_test_cases_api.py`
- Test: `backend/tests/test_stats_cache.py`

**Interfaces:**
- Produces:
  - `facts_cache_key(project_id: str) -> str` = `f"cache:{project_id}:stats-facts"`
  - `class FactsCache: __init__(self, redis: Redis, project_id: str, ttl_seconds: int)`; `read(self, load: Callable[[], ProjectFacts]) -> ProjectFacts` (giống `CachedList.read`: get → nếu trống thì nhớ generation, `load()`, `set_if_unchanged`); `invalidate(self) -> None`.
  - `invalidate_project_stats(redis: Redis, project_id: str) -> None`
  - `ResultRepository(gateway, spreadsheet_id, *, redis: Redis, project_id: str)` — tham số mới **bắt buộc**; `append_batch` gọi `invalidate_project_stats` sau khi ghi.
  - `TestCaseRepository`: thay 3 chỗ `self._cache.invalidate()` bằng `self._after_write()` (xoá cache danh sách **và** `invalidate_project_stats`). Comment rõ: "mọi hàm ghi mới phải gọi `_after_write()`".
  - `Settings.stats_cache_ttl_seconds: int = 600`; `Services.stats_cache_ttl_seconds: int = 600` (truyền từ settings trong `build_services`).
  - `load_facts(services: Services, scope: ProjectScope) -> ProjectFacts` trong `backend/app/api/project_facts.py` (mới): `FactsCache(...).read(lambda: facts_from(scope.test_cases.list_all(), scope.results.list_all()))`.

- [ ] **Step 1: Test đỏ** `test_stats_cache.py` (dùng fixture `app`, `gateway`, `make_project`):
  - `test_second_read_does_not_touch_sheets`: `load_facts` hai lần → lần 2 `gateway.calls` không tăng.
  - `test_appending_result_invalidates_facts`: đọc, `scope.results.append_batch([fail])`, đọc lại → có kết quả mới.
  - `test_saving_case_invalidates_facts`: đọc, `scope.test_cases.save(... APPROVED)`, đọc lại → trạng thái mới.
  - `test_write_during_load_is_not_cached`: dùng `gateway.after_next_read` để ghi kết quả ngay sau lúc đọc tab Results → lần đọc kế tiếp phải thấy kết quả mới (cache không lưu bản cũ).
- [ ] **Step 2:** `uv run pytest tests/test_stats_cache.py -q` → FAIL.
- [ ] **Step 3:** Cài đặt; sửa `RunRepository.__init__` truyền `redis=redis, project_id=project_id` cho `ResultRepository` bên trong; sửa `scope_for`; sửa 4 chỗ test dựng `ResultRepository(gateway, SHEET)` thành có `redis=redis, project_id=...` (lấy fixture `redis`).
- [ ] **Step 4:** Chạy cả bộ backend → PASS.
- [ ] **Step 5: Commit** `feat(backend): cache số liệu project, xoá khi ghi case hoặc kết quả`.

> Ghi chú khi gộp với nhánh nhập Excel: `TestCaseRepository.create_many` của nhánh đó gọi `self._cache.invalidate()` — đổi thành `self._after_write()`.

### Task 7: API `GET /projects/{id}/stats` và `/leaderboard`

**Files:**
- Create: `backend/app/api/routers/stats.py` (prefix `/api/projects/{project_id}`, tag `stats`)
- Modify: `backend/app/main.py` (`include_router(stats.router)`)
- Test: `backend/tests/test_stats_api.py`

**Interfaces:**
- Consumes: `load_facts` (Task 6), `project_stats`, `leaderboard`, `Period` (Task 5), `load_project(..., Action.VIEW_PROJECT)`.
- Produces:
  - `GET /api/projects/{project_id}/stats -> ProjectStats` (tên màn hình từ `scope.screens.list_all()`).
  - `GET /api/projects/{project_id}/leaderboard?period=week|month|all -> Leaderboard` (mặc định `week`; tên từ `services.users.list_all()`; `me = user.email`).

- [ ] **Step 1: Test đỏ:**
  - `test_member_sees_project_stats`: tester thành viên, 1 case APPROVED + 1 FAIL tay → 200, `total_cases 1`, `open_bugs 1`.
  - `test_non_member_gets_404`: tester không là thành viên → 404 cho cả hai API.
  - `test_admin_sees_any_project_stats` → 200.
  - `test_leaderboard_returns_names_not_result_details`: JSON chỉ có các khoá `period, cases, bugs`; mỗi dòng chỉ có `rank, email, name, count`.
  - `test_leaderboard_rejects_unknown_period`: `?period=year` → 422.
  - `test_manual_result_updates_stats_right_away`: gọi stats, `POST /api/projects/{id}/test-cases/{case}/results` FAIL (theo mẫu trong `test_manual_results_api.py`), gọi lại stats → `open_bugs` tăng.
- [ ] **Step 2:** Chạy → FAIL (404 route).
- [ ] **Step 3:** Cài đặt router.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(backend): API số liệu và bảng xếp hạng project`.

### Task 8: API `GET /me/pet` và `/me/dashboard` + sinh kiểu cho frontend

**Files:**
- Modify: `backend/app/api/routers/me.py`, `backend/app/core/models/stats.py`
- Modify (sinh ra): `frontend/lib/api/openapi.json`, `frontend/lib/api/schema.d.ts`, `frontend/lib/api/types.ts`
- Test: `backend/tests/test_pet_api.py`

**Interfaces:**
- Produces:
  - `ProjectProgress(project_id: str, project_name: str, done: int, total: int)`; `MyDashboard(projects: list[ProjectProgress], daily: list[DayCount])`
  - `GET /api/me/pet -> MyPet` — project tính: Admin = mọi project; người khác = `members.projects_of(email)` (gồm cả project đã lưu trữ, để nhím không "teo" khi project bị lưu trữ — quyết định của người viết plan).
  - `GET /api/me/dashboard -> MyDashboard` — project đang hoạt động (không lưu trữ) mà người đó là thành viên; Admin = mọi project chưa lưu trữ.
  - Mỗi project bọc `try/except (SheetAccessDeniedError, MissingColumnsError)` + `logger.warning`, giống `my_overview`.
  - `types.ts` thêm: `MyPet, PetMood, MyDashboard, ProjectProgress, DayCount, ProjectStats, ScreenProgress, Leaderboard, LeaderboardRow, Board, Period`.

- [ ] **Step 1: Test đỏ:**
  - `test_pet_counts_bugs_in_my_projects_only`: An là thành viên A, không phải B; An có 3 bug ở A, 2 ở B → `bugs == 3`.
  - `test_new_user_pet_is_baby_and_normal`: chưa làm gì → `level 1, bugs 0, bugs_to_next 5, streak 0, mood "NORMAL"`.
  - `test_pet_happy_after_catching_bug_today`: ghi FAIL tay hôm nay → `mood "HAPPY"`, `streak 1`.
  - `test_dashboard_lists_progress_and_14_days`: 2 project → `len(projects) == 2`, `len(daily) == 14`.
  - `test_broken_project_sheet_is_skipped`: `gateway.denied.add(SHEET_B)` → `/me/pet` và `/me/dashboard` vẫn 200, chỉ đếm project A.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt trong `me.py` (dùng `scope_for` + `load_facts`; ngày = `today_in_vietnam()`).
- [ ] **Step 4:** PASS; chạy cả bộ backend.
- [ ] **Step 5:** `cd frontend && npm run gen:api`; thêm các alias vào `lib/api/types.ts`; `npx tsc --noEmit` xanh.
- [ ] **Step 6: Commit** `feat(backend): API nhím và tổng quan của tôi`. Cập nhật Tiến độ + HANDOFF, **dừng đợt 2**.

---

## Đợt 3 — Tổng quan project + đồ thị Tổng quan chung

### Task 9: Recharts + các component đồ thị

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json` (`npm install recharts` — ghi phiên bản cài được vào ghi chú đợt)
- Create: `frontend/components/charts/pass-fail-chart.tsx` (default export), `frontend/components/charts/case-status-donut.tsx` (default export), `frontend/components/charts/progress-list.tsx`, `frontend/components/charts/lazy.tsx`
- Test: `frontend/components/charts/charts.test.tsx`

**Interfaces:**
- Consumes: `DayCount`, `ProjectStats["case_status"]` (Task 8).
- Produces:
  - `PassFailChart({ days }: { days: DayCount[] })` — cột chồng Pass/Fail/Khác, màu `var(--chart-pass|fail|other)`, trục ngày `dd/MM`.
  - `CaseStatusDonut({ counts }: { counts: Record<"DRAFT"|"IN_REVIEW"|"APPROVED"|"TESTED", number> })` — màu `var(--chart-1..4)`.
  - `ProgressList({ items }: { items: { id: string; label: string; done: number; total: number }[] })` — thanh ngang bằng div (không cần Recharts), `role="progressbar"` + `aria-valuenow`.
  - `lazy.tsx`: `LazyPassFailChart`, `LazyCaseStatusDonut` = `next/dynamic(..., { ssr: false, loading: () => <Skeleton className="h-56 w-full" /> })`.
  - Mỗi đồ thị bọc trong `<figure aria-label=...>` kèm `<figcaption className="sr-only">` tóm tắt bằng chữ (ví dụ "14 ngày: 12 Pass, 3 Fail, 1 Khác"); dữ liệu toàn 0 → hiện chữ `charts.empty` ("Chưa có dữ liệu") thay đồ thị.
  - Chuỗi tiếng Việt nhóm `charts` trong `vi.json`.

- [ ] **Step 1: Test đỏ** (`ResponsiveContainer` không đo được trong jsdom: mock `ResizeObserver` trong test hoặc truyền `width/height` cố định khi `process.env.NODE_ENV === "test"` — chọn một cách, ghi comment):
  - `it("PassFailChart tóm tắt tổng Pass/Fail/Khác")` → thấy "12 Pass, 3 Fail, 1 Khác".
  - `it("PassFailChart toàn số 0 thì hiện Chưa có dữ liệu")`.
  - `it("CaseStatusDonut tóm tắt từng trạng thái")`.
  - `it("ProgressList hiện done/total và phần trăm, total 0 không chia cho 0")` → `aria-valuenow="0"`.
- [ ] **Step 2:** `npx vitest run components/charts` → FAIL.
- [ ] **Step 3:** Cài recharts, viết component.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(frontend): thêm component đồ thị dùng màu theo giao diện`.

### Task 10: Trang Tổng quan project

**Files:**
- Create: `frontend/app/(app)/projects/[projectId]/overview/page.tsx`, `frontend/lib/use-stats.ts`
- Modify: `frontend/app/(app)/projects/[projectId]/page.tsx` (chuyển sang `/overview`), `frontend/lib/project-tabs.ts` (tab `{ segment: "overview", labelKey: "overview", permission: "VIEW_PROJECT" }` đứng đầu), `frontend/messages/vi.json` (`projectTabs.overview: "Tổng quan"`, nhóm `projectOverview`)
- Test: `frontend/app/(app)/projects/[projectId]/overview/page.test.tsx`, `frontend/lib/project-tabs.test.ts`

**Interfaces:**
- Consumes: API Task 7–8; component Task 9.
- Produces (`lib/use-stats.ts`, react-query, `unwrap(await api.GET(...))` như `use-overview.ts`):
  - `useProjectStats(projectId: string)` — key `["projects", projectId, "stats"]`
  - `useLeaderboard(projectId: string, period: Period)` — key `["projects", projectId, "leaderboard", period]`
  - `useMyDashboard()` — key `["me", "dashboard"]`
  - `useMyPet()` — key `["me", "pet"]`
  - Sau khi ghi kết quả tay / lưu case thành công: thêm `queryClient.invalidateQueries({ queryKey: ["projects", projectId, "stats"] })`, `["projects", projectId, "leaderboard"]`, `["me", "pet"]`, `["me", "dashboard"]` ở hook ghi tương ứng (`lib/use-manual-result.ts`, `lib/use-test-cases.ts`).

- [ ] **Step 1: Test đỏ** (mock `@/lib/use-stats` và `@/components/charts/lazy` thành component đơn giản in props):
  - `it("hiện 3 thẻ số: tổng case, % Pass, bug đang mở")` → "128", "82%", "14".
  - `it("pass_rate null thì hiện dấu gạch")` → "—".
  - `it("có đồ thị Pass/Fail, vòng trạng thái và tiến độ màn hình")`.
  - `project-tabs.test.ts`: `PROJECT_TABS[0].segment === "overview"`.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt trang (chỗ bảng xếp hạng để trống, Task 14 điền). Bố cục: thẻ số 3 cột (1 cột ở điện thoại), đồ thị Pass/Fail rộng 2/3 + donut 1/3, tiến độ màn hình bên dưới.
- [ ] **Step 4:** PASS; mở trình duyệt kiểm tra cả 3 giao diện, bề ngang 375px không cuộn ngang.
- [ ] **Step 5: Commit** `feat(frontend): trang Tổng quan project có đồ thị`.

### Task 11: Đồ thị ở Tổng quan chung

**Files:**
- Modify: `frontend/app/(app)/page.tsx`, `frontend/messages/vi.json` (nhóm `overview`)
- Test: `frontend/app/(app)/page.test.tsx`

**Interfaces:**
- Consumes: `useMyDashboard` (Task 10), `ProgressList`, `LazyPassFailChart` (Task 9).
- Produces: mục "Tiến độ dự án" + "Kết quả 14 ngày" cho **mọi vai trò** (kể cả Viewer: thay câu `viewerEmpty` bằng hai mục này khi có dữ liệu). Chừa chỗ đầu trang cho thẻ nhím (Task 13).

- [ ] **Step 1: Test đỏ** (thêm mock `@/lib/use-stats` và `@/components/charts/lazy`):
  - `it("mọi vai trò thấy tiến độ từng dự án")` với role TESTER và VIEWER → thấy tên "Dự án A".
  - `it("các thẻ cũ theo vai trò vẫn còn")` — giữ nguyên test cũ xanh.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(frontend): đồ thị tiến độ và kết quả ở Tổng quan`. Cập nhật Tiến độ + HANDOFF, **dừng đợt 3**.

---

## Đợt 4 — Nhím + chuỗi ngày

### Task 12: Component `Hedgehog`

**Files:**
- Create: `frontend/components/pet/hedgehog.tsx`, `frontend/components/pet/hedgehog.css` (hoặc keyframes trong `globals.css` dưới tên `hh-bounce`, `hh-blink`)
- Test: `frontend/components/pet/hedgehog.test.tsx`

**Interfaces:**
- Consumes: `PetMood` (Task 8).
- Produces: `Hedgehog({ level, mood, className }: { level: 1 | 2 | 3 | 4; mood: PetMood; className?: string })` — `<svg role="img" aria-label="Nhím {tên cấp}, {biểu cảm}">`, `viewBox="0 0 200 170"`, chiều rộng theo cấp `96 / 128 / 160 / 192` px. Hình vẽ kiểu C: chép hàm `spikes()` và các phần mặt/biểu cảm từ `.superpowers/brainstorm/694-1795094950/content/nhim-style.html` (kiểu `C`), đổi sang JSX; `id` gradient dùng `useId()` để nhiều nhím trên một trang không đè nhau. Cấp 4 có vương miện (`data-testid="crown"`). Cấp cao hơn gai dài/nhiều hơn (người làm tự vẽ). Hoạt ảnh: cả con nhún nhảy 2.4s, mắt chớp mỗi ~4s (chỉ biểu cảm NORMAL/HUNGRY có mắt tròn); tắt trong `@media (prefers-reduced-motion: reduce)`.

- [ ] **Step 1: Test đỏ:**
  - `it("mỗi biểu cảm có nhãn riêng")`: render 4 mood → `getByRole("img", { name: /Cười|Bình thường|Đói|Khóc/ })`.
  - `it("chỉ Vua nhím đội vương miện")`: level 4 có `crown`, level 3 không.
  - `it("nhím lớn dần theo cấp")`: width level 1 < level 4.
  - `it("hai con nhím trên một trang không trùng id gradient")`.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(frontend): vẽ con nhím SVG có 4 biểu cảm`.

### Task 13: Thẻ "Nhím của tôi" ở Tổng quan chung

**Files:**
- Create: `frontend/components/pet/pet-card.tsx`
- Modify: `frontend/app/(app)/page.tsx`, `frontend/messages/vi.json` (nhóm `pet`)
- Test: `frontend/components/pet/pet-card.test.tsx`

**Interfaces:**
- Consumes: `useMyPet` (Task 10), `Hedgehog` (Task 12).
- Produces: `PetCard()` — khung `bg-card`, hiện nhím, tên cấp (`pet.level.1..4`: Nhím con / Nhím nhỡ / Nhím trưởng thành / Vua nhím), "🔥 {streak} ngày", số bug, thanh tiến độ "Còn {n} bug nữa lên cấp" (cấp 4: "Cấp cao nhất rồi!"), một câu theo biểu cảm (`pet.moodText.HAPPY` "Hôm nay bắt được bug, nhím vui lắm!", `NORMAL` "Nhím đang chờ bạn bắt bug.", `HUNGRY` "Nhím đói rồi, bắt bug cho nhím ăn nhé!", `CRY` "Lâu quá chưa gặp, nhím khóc mất rồi…"). Đặt ở đầu trang Tổng quan chung cho mọi vai trò.

- [ ] **Step 1: Test đỏ:**
  - `it("hiện chuỗi ngày và số bug còn thiếu")`: `{level 2, bugs 7, bugs_to_next 13, streak 4, mood "NORMAL"}` → "4 ngày", "Còn 13 bug nữa lên cấp".
  - `it("Vua nhím không còn thanh lên cấp")`.
  - `it("nhím đói có câu nhắc")`.
  - `it("đang tải thì hiện khung xương, không vỡ")`.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt; thêm vào `page.tsx` (cập nhật mock trong `page.test.tsx`).
- [ ] **Step 4:** PASS; kiểm tra trình duyệt ở 3 giao diện và bật "giảm chuyển động" của hệ điều hành.
- [ ] **Step 5: Commit** `feat(frontend): thẻ Nhím của tôi ở Tổng quan`. Cập nhật Tiến độ + HANDOFF, **dừng đợt 4**.

---

## Đợt 5 — Bảng xếp hạng

### Task 14: Hai bảng xếp hạng ở Tổng quan project

**Files:**
- Create: `frontend/components/leaderboard/leaderboard-card.tsx`, `frontend/components/leaderboard/project-leaderboards.tsx`
- Modify: `frontend/app/(app)/projects/[projectId]/overview/page.tsx`, `frontend/messages/vi.json` (nhóm `leaderboard`)
- Test: `frontend/components/leaderboard/leaderboard.test.tsx`

**Interfaces:**
- Consumes: `useLeaderboard`, `useMe`, `Board`, `Period` (Task 8, 10).
- Produces:
  - `LeaderboardCard({ title, board, meEmail }: { title: string; board: Board; meEmail: string })` — top 5 với 🥇🥈🥉 cho hạng 1–3, dòng của mình in đậm màu `text-primary` + "(bạn)"; `board.me` có thì hiện thêm sau dấu "…" (rank `null` → "Chưa có điểm"); bảng trống → "Chưa ai có điểm — bạn là người đầu tiên nhé!".
  - `ProjectLeaderboards({ projectId })` — nút chọn Tuần này / Tháng này / Tất cả (mặc định Tuần này) + hai thẻ "Viết case nhiều nhất", "Bắt bug nhiều nhất".

- [ ] **Step 1: Test đỏ:**
  - `it("hiện huy chương cho 3 hạng đầu")`.
  - `it("đánh dấu dòng của chính mình")`.
  - `it("người xem ngoài top hiện thêm dòng của mình")`.
  - `it("bằng điểm thì cùng hạng")`: hai dòng rank 1 đều có 🥇.
  - `it("đổi bộ lọc thì gọi useLeaderboard với period mới")`.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt; gắn vào trang Tổng quan project.
- [ ] **Step 4:** PASS; kiểm tra trình duyệt.
- [ ] **Step 5: Commit** `feat(frontend): bảng xếp hạng viết case và bắt bug`. Cập nhật Tiến độ + HANDOFF, **dừng đợt 5**.

---

## Đợt 6 — Nút nhạc

### Task 15: Bài nhạc + trình phát dùng chung

**Files:**
- Create: `frontend/public/music/*.mp3` (2–3 bài), `frontend/public/music/LICENSE.md`, `frontend/lib/music/tracks.ts`, `frontend/components/music/music-provider.tsx`
- Modify: `frontend/app/(app)/layout.tsx` (bọc `<MusicProvider>` quanh `<AppShell>`)
- Test: `frontend/components/music/music-provider.test.tsx`

**Interfaces:**
- Produces:
  - `TRACKS: { title: string; src: string }[]` (`src` = `/music/<file>.mp3`).
  - `MusicProvider({ children })` — render đúng **một** `<audio preload="none">`; context giá trị `{ playing: boolean; track: number; volume: number; toggle(): void; next(): void; setVolume(v: number): void }`.
  - `useMusic(): MusicContextValue | null` — ngoài provider trả `null`.
  - `localStorage` khoá `music:volume` (0–1, mặc định 0.4) và `music:track`; đọc/ghi bọc `try/catch`. Không lưu "đang phát": tải lại trang luôn ở trạng thái dừng (spec 6.7: bấm lại mới phát).
  - Hết bài tự sang bài kế (`onEnded` → `next()`), quay vòng.
- Nguồn nhạc: chỉ bài giấy phép **CC0 / Pixabay Content License** (dùng được không cần ghi công). `LICENSE.md` ghi tên bài, tác giả, link gốc, giấy phép. Không tải được bài (không có mạng) → dừng task, nhờ chủ dự án chép file vào `frontend/public/music/`. Mỗi file ≤ 5 MB.

- [ ] **Step 1: Test đỏ** (mock `HTMLMediaElement.prototype.play` trả `Promise.resolve()`, `pause` là `vi.fn()`):
  - `it("không tự phát khi mở trang")`: render → `play` chưa được gọi; `audio.preload === "none"`.
  - `it("toggle phát rồi dừng")`.
  - `it("next quay vòng danh sách bài")`.
  - `it("nhớ âm lượng sau khi tải lại")`.
  - `it("localStorage bị chặn vẫn chạy được")`: `vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error() })` → không lỗi.
  - `it("play bị trình duyệt từ chối thì về trạng thái dừng")`: `play` trả `Promise.reject()` → `playing === false`.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt; tải nhạc + viết `LICENSE.md`.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(frontend): trình phát nhạc lofi dùng chung cho mọi trang`.

### Task 16: Nút nhạc trên thanh đầu trang

**Files:**
- Create: `frontend/components/music/music-button.tsx`
- Modify: `frontend/components/app-shell/topbar.tsx`, `frontend/messages/vi.json` (nhóm `music`)
- Test: `frontend/components/music/music-button.test.tsx`

**Interfaces:**
- Consumes: `useMusic`, `TRACKS` (Task 15).
- Produces: `MusicButton()` — ngoài provider render `null` (test Topbar cũ không cần sửa). Nút tròn ▶/⏸ (`aria-label` "Phát nhạc"/"Dừng nhạc"), cạnh đó nút mũi tên mở popover nhỏ: tên bài đang chọn, nút "Bài tiếp", thanh âm lượng `<input type="range" min=0 max=1 step=0.05>`. Đặt trước `NotificationBell`.

- [ ] **Step 1: Test đỏ:**
  - `it("bấm nút thì gọi toggle và đổi nhãn")`.
  - `it("ngoài MusicProvider thì không hiện gì")`.
  - `it("kéo âm lượng gọi setVolume")`.
- [ ] **Step 2:** Chạy → FAIL.
- [ ] **Step 3:** Cài đặt; gắn vào Topbar.
- [ ] **Step 4:** PASS; chạy cả hai bộ test; mở trình duyệt: bấm phát, chuyển trang (nhạc không ngắt), tải lại (không tự phát), đổi 3 giao diện (nút đổi màu theo).
- [ ] **Step 5: Commit** `feat(frontend): nút phát nhạc trên thanh đầu trang`. Cập nhật Tiến độ + HANDOFF, báo chủ dự án toàn bộ đã xong, **dừng**. Gợi ý bước tiếp: viết ghi chú học (skill `writing-learning-notes`), hỏi chủ dự án về gộp nhánh.

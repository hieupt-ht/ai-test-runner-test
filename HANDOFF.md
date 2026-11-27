# HANDOFF — đọc file này đầu tiên

Cập nhật: 2026-11-19. Nhánh hiện tại: `feature/ai-agent-runner` (từ `develop`). **Không push, không tạo PR khi chưa được chủ dự án đồng ý.**

## Dự án đang ở đâu

AI Test Runner là web app nội bộ cho QA: Tester viết case, QA Lead duyệt, dữ liệu chính nằm trong Google Sheets. Case `APPROVED` được tạo thành GitHub issue trong **repo của dự án**. Codex chạy **ngoài** ứng dụng: đọc issue qua GitHub MCP, chạy Playwright, comment kết quả lên issue và gọi API token riêng để ghi tab `Runs`/`Results`.

M1–M3 đã nằm ở `develop`. Kế hoạch mới ở `docs/superpowers/plans/2026-11-14-case-to-issue-and-codex-agent.md`, thiết kế ở `docs/superpowers/specs/2026-11-14-case-to-issue-and-codex-agent-design.md`. Hướng worker Playwright cũ được giữ ở nhánh `feature/m4-playwright-worker` và tag `m4-playwright-v1`; **không** có worker hay tab Chạy test trên nhánh hiện tại. Chỉ mô hình và repository `Runs`/`Results` được lấy lại từ tag để phục vụ API agent.

Kế hoạch thông báo và bảng kết quả ở `docs/superpowers/plans/2026-11-14-notifications-results-dashboard.md` đã hoàn thành đủ 10 task. Ứng dụng hiện có chuông thông báo, trang Kết quả, hai tab "Đang làm"/"Đã xong", trang Tổng quan theo vai trò và hộp thoại dùng tốt hơn trên màn hình hẹp. Thông báo lưu trong Redis 30 ngày, tối đa 100 cái mỗi người; mất thông báo không làm mất dữ liệu chính. Cách cấu hình Codex và prompt mẫu ở `docs/codex-agent.md`. Tính năng **Chạy lại** đã xong: nút ở trang Kết quả (QA Lead/Admin) gọi `POST /api/projects/{project_id}/test-cases/{case_id}/request-rerun`, app comment + mở lại issue + gắn nhãn `needs-rerun`; khi có kết quả mới app tự bỏ nhãn này. Đã chạy thử trên repo thật `hieupt-ht/ShopHub` (RUN-0005). Codex **không** tự comment lên issue, app làm việc đó bằng GitHub App. Kiểm tra cuối: backend **388 test**, frontend **105 test** qua; `mypy app`, `ruff check`, typecheck, lint và build đều sạch.

## Đã xong (2026-11-27): nhập kết quả từ Excel — Phần 1 (nhánh `feature/import-results`, chưa push)

- Tester tự tạo module (tên không trùng) và tự nhận luôn, hạn hôm nay + 7 ngày; nhận lỗi thì xoá module vừa tạo. Đổi tên/xoá module vẫn chỉ QA.
- Kết quả Fail chạy tay không còn bắt buộc ảnh/video (DECISIONS số 43); panel chỉ nhắc màu vàng.
- Nút "Nhập từ Excel" hiện cho mọi người tạo được case; trang Màn hình có "Thêm module" cho tester; hộp thoại nhập có lối tắt "+ Tạo module mới".
- **Còn chờ:** Phần 2 (cột kết quả trong Excel, lưu kết quả chờ, chạy hàng loạt, nút "Lưu và chạy") — cần kế hoạch riêng, xem `docs/superpowers/specs/2026-11-27-import-results-batch-run-design.md` mục 4.

## Đã xong (2026-11-26): chia việc theo module

Thiết kế `docs/superpowers/specs/2026-11-26-modules-design.md`, kế hoạch `docs/superpowers/plans/2026-11-26-modules.md` (8 task, làm kiểu tự làm một mạch trên nhánh `feature/modules`, chưa push).

- **Ý tưởng:** QA chia việc theo **module** (nhóm màn hình) thay vì từng màn hình. Việc giao theo màn hình (`Assignments`) giữ nguyên và vẫn quyết định quyền, kết quả, thông báo; module chỉ tự sinh/xoá các dòng đó.
- **Dữ liệu:** Sheet dự án có thêm tab `Modules`, `ModuleAssignments` và cột `module_id` ở `Screens` (app tự thêm khi khởi động, Sheet cũ không cần sửa tay).
- **Luồng dùng:** QA tạo module (trang Màn hình) → gán màn hình vào module → **Giao** cho tester, hoặc tester tự bấm **Nhận**. Module đã có người làm chỉ hiện dòng đỏ cảnh báo, vẫn nhận được (backend không chặn). **Bỏ nhận** xoá việc giao màn hình của module, test case đã viết vẫn còn.
- **Import:** hộp thoại "Nhập từ Excel" bắt chọn module trước. Tên màn hình chưa có trong module được **tự tạo** (không báo lỗi như trước) và tự giao cho người đang làm module. Tester phải nhận module trước khi nhập. Chọn "Không theo module (như cũ)" thì chạy đúng luồng cũ.
- **Khoá:** thứ tự luôn là screens → assignments → module-assignments → test-cases (`ModuleAssignmentRepository` có khoá riêng, khác bản thiết kế ghi dùng chung).
- **Kiểm tra:** backend 911 test, frontend 373 test qua; ruff, lint, typecheck sạch. Test frontend mặc định hết 5 giây thì lỗi giả trên máy chậm, chạy `npx vitest run --testTimeout=60000`.

## Đã xong (2026-11-19): nhập test case từ Excel

Thiết kế `docs/superpowers/specs/2026-11-19-import-test-cases-design.md`, kế hoạch `docs/superpowers/plans/2026-11-19-import-test-cases.md` (10 task / 3 đợt, làm kiểu subagent: mỗi task một người làm + một người kiểm tra).

- **Đợt 1 xong** (Task 1–3, commit `22cd6ba`, `13b1410`, `6f3aedb`): trạng thái việc đếm mọi case của màn hình (nhãn WRITING = "Đang làm"); tách `can_edit` (người tạo / lead) và `can_run` (thêm tester được giao màn hình; `Action.RUN_TEST_CASE`); kết quả test tay FAIL bắt buộc có ít nhất một ảnh/video (422); trang case hiện khung chạy cho người chỉ được chạy. Backend **743 test**, frontend **272 test**, mypy/ruff/tsc/eslint sạch.
- **Đợt 2 xong** (Task 4–7, backend; commit `bfd4b2c`+`192fdcb`, `2759e9f`, `b3e9448`+`6d45ff1`, `c78d01c`): `case_import.py` đọc file .xlsx theo 16 cột (chặn file >2 MB, >2000 dòng, >300 case, dừng đọc sớm); `next_ids`/`create_many`/`record_many` ghi một lô; `TestCaseService.preview_import`/`import_cases` (kiểm tra trong khoá assignments→test-cases, có lỗi thì không ghi gì, audit/trạng thái/thông báo sau khi ghi chỉ log nếu lỗi); API `GET .../test-cases/import/template`, `POST .../import/preview`, `POST .../import` (422 `{detail, errors}`, 409 khoá bận, 503 lỗi Sheet; file rỗng báo "File không có test case nào"). Backend **798 test**, mypy/ruff sạch; API types đã sinh lại. Việc nhỏ chưa sửa (ghi ở sổ SDD): chuẩn hoá NFC chữ có dấu, `_refresh_status` chưa bắt lỗi mạng ngoài HttpError.
- **Đợt 3 xong** (Task 8–10, frontend + tài liệu; commit `25d12ae`, `3082672`, `62044d6`, docs): hook `use-case-import`, nút "Nhập từ Excel" ở trang danh sách case mở hộp thoại (tải file mẫu, chọn file, xem trước lỗi/cảnh báo, "Nhập N case"). Hướng dẫn cho QA/tester: `docs/huong-dan-nhap-test-case.md`.
- **Thay đổi hành vi cần biết:** (1) khoá case: tester chỉ **sửa** case mình tạo, case người khác viết chỉ **chạy** được (tester B được giao màn hình không còn sửa được case của tester A); (2) trạng thái việc của màn hình đếm mọi case chưa ngừng dùng, ai tạo cũng tính; (3) nhãn `WRITING` hiển thị là "Đang làm" (giá trị trong Sheet/API giữ nguyên); (4) FAIL ở test tay bắt buộc có ảnh/video.
- **Việc còn lại:** review cả nhánh (các việc nhỏ hoãn lại ghi ở sổ SDD `.superpowers/sdd/2026-11-19-import-test-cases/progress.md`); chạy thử app bằng trình duyệt thật, chụp màn hình ở 1366×768 (cần dữ liệu Google thật, chưa làm).
- **Cần xem lại:** `backend/app/api/routers/me.py` `case_counts` vẫn lọc theo `created_by`, lệch luật trạng thái mới (thẻ "Việc của tôi" có thể đếm ít hơn trạng thái).

## Đang làm (2026-11-19): giao diện vui + nhím bug

Nhánh `feature/fun-ui` (tách từ `feature/ai-agent-runner`). Spec `docs/superpowers/specs/2026-11-19-giao-dien-vui-nhim-bug-design.md`, kế hoạch `docs/superpowers/plans/2026-11-19-giao-dien-vui-nhim-bug.md` (6 đợt, làm từng đợt).

- **Đợt 1 xong** (Task 1–2): giao diện thứ 3 "Kẹo ngọt" (lớp `.candy` trong `globals.css`, mục menu trong Topbar) và 3 màu đồ thị `--chart-pass/fail/other` cho cả 3 giao diện. Việc chủ dự án cần làm: bật Kẹo ngọt rồi xem các màn hình xem có chỗ chìm màu không.
- **Đợt 2 xong** (Task 3–8; 2026-11-20): backend số liệu. Hàm thuần trong `app/core/services/stats.py` (bug bắt được, chuỗi ngày, cấp/biểu cảm nhím, thẻ số, đồ thị 14 ngày, xếp hạng); cache `ProjectFacts` ở `app/core/stats_cache.py` (10 phút, xoá ngay khi ghi case/kết quả qua `TestCaseRepository._after_write()` và `ResultRepository.append_batch`); 4 API: `GET /api/projects/{id}/stats`, `/leaderboard?period=`, `GET /api/me/pet`, `/api/me/dashboard`. `ResultRepository` giờ **bắt buộc** `redis=` và `project_id=`. Kiểu frontend đã sinh lại (`npm run gen:api`). Backend 848 test qua. Khi gộp nhánh nhập Excel: `create_many` của nhánh đó phải gọi `_after_write()`.
- **Đợt 3 xong** (Task 9–11; 2026-11-20): frontend có Recharts `^3.11.0` (tải động qua `components/charts/lazy.tsx`), 3 component đồ thị (`pass-fail-chart`, `case-status-donut`, `progress-list`), hook `lib/use-stats.ts` (`useProjectStats`, `useLeaderboard`, `useMyDashboard`, `useMyPet`), trang `projects/[projectId]/overview` (tab Tổng quan đứng đầu, mở project là vào trang này), và mục "Tiến độ dự án" + "Kết quả 14 ngày" ở Tổng quan chung cho mọi vai trò. Ghi case/kết quả làm mới thêm `["me","pet"]` và `["me","dashboard"]`. Backend 848 test, frontend 315 test qua (`case-form.test` đôi khi quá hạn 5 giây khi máy chậm, chạy lại là qua), tsc/eslint sạch. Chưa xem bằng trình duyệt thật ở 3 giao diện.
- **Đợt 4 xong** (Task 12–13; 2026-11-20): `components/pet/hedgehog.tsx` (nhím SVG, 4 cấp to dần, vương miện cấp 4, 4 biểu cảm, nhún nhảy + chớp mắt, tắt khi giảm chuyển động) và `pet-card.tsx` (cấp, 🔥 chuỗi ngày, số bug, thanh lên cấp, câu theo tâm trạng) đặt đầu Tổng quan chung cho mọi vai trò. Frontend 323 test, backend 848 test qua (lần chạy đầu có 4 test quá hạn do máy chậm, chạy lại qua hết). Chưa xem bằng trình duyệt thật.
- **Đợt 5 xong** (Task 14; 2026-11-20): `components/leaderboard/` có `LeaderboardCard` (top 5, 🥇🥈🥉, dòng của mình in đậm + "(bạn)", ngoài top thì hiện thêm sau "…") và `ProjectLeaderboards` (Tuần này/Tháng này/Tất cả) gắn cuối Tổng quan project. Frontend 330 test, backend 848 test qua (1 test case-form quá hạn do máy chậm lần chạy cả bộ, chạy riêng thì qua). Chưa xem bằng trình duyệt thật.
- **Đợt 6 xong** (Task 15–16; 2026-11-20): `MusicProvider` (một thẻ `<audio preload="none">` bọc ngoài AppShell nên chuyển trang nhạc không ngắt, không tự phát, nhớ âm lượng/bài trong localStorage) và `MusicButton` trên topbar (▶/⏸ + menu nhỏ: tên bài, Bài tiếp, âm lượng). Hai bài CC0 từ OpenGameArt trong `frontend/public/music/` (ghi nguồn ở `LICENSE.md`). Frontend 340 test, backend 848 test qua. **Cả 6 đợt xong.** Chưa xem bằng trình duyệt thật (3 giao diện, 375px, giảm chuyển động); còn review cả nhánh và quyết định gộp nhánh.
- Frontend có sẵn 4 test hay quá hạn 5 giây khi máy chậm (create-project, reset-password, change-password, case-form); chạy lẻ từng file thì qua.

## Đang làm (2026-11-16)

Bằng chứng ảnh/video (Cloudinary), test Android/iOS, giao bug cho dev. Thiết kế: `docs/superpowers/specs/2026-11-16-evidence-mobile-and-bug-assignment-design.md`. Kế hoạch 27 task, 8 đợt: `docs/superpowers/plans/2026-11-16-evidence-mobile-and-bug-assignment.md`. **Làm từng đợt một**: xong đợt thì đánh dấu `[x]` trong kế hoạch, ghi tiến độ ở đây, dừng cho chủ dự án `/compact`.

- Tiến độ: **đợt 1 xong** (Task 1–5, dữ liệu và mô hình; 2026-11-16): app tự thêm cột mới vào cuối tiêu đề Sheet lúc khởi động, có kiểu `Media`, cột mới của Projects/Screens/TestCases/Runs/Results. Backend 405 test, frontend 105 test qua. **Đợt 2 xong** (Task 6–9; 2026-11-17): công tắc "Cần QA duyệt" (tắt thì gửi là duyệt luôn, các case đang chờ được duyệt một lượt), sửa case đã duyệt tại chỗ kèm comment/`needs-rerun` lên issue, nút Duyệt/Trả lại mờ, lịch sử có phiên bản và giờ Việt Nam. Backend 431 test, frontend 112 test qua. Lưu ý: dự án cũ chưa có cột `require_review` đọc ra là TẮT duyệt. **Đợt 3 xong** (Task 10–13; 2026-11-17): backend ký upload Cloudinary (tester và agent), kiểm tra link ảnh đúng cloud, tự xoá file khi bỏ khỏi case; frontend có `MediaPicker` và form case 2 cột. Backend 453 test, frontend 134 test qua. Chưa kiểm tra bằng trình duyệt thật (1366×768, không cuộn cả trang). **Đợt 4 xong** (Task 14; 2026-11-17): issue có phiên bản case, nền tảng, loại test, regression, điểm bắt đầu, mã app Android/iOS, ảnh hướng dẫn và 6 ảnh cắt từ video; cập nhật issue giữ nhãn kết quả (`needs-rerun`, `test: fail`...) và nhãn tay. Backend 471 test qua. **Đợt 5 xong** (Task 15–20; 2026-11-17): Codex gửi được kết quả từng bước, video, ảnh, môi trường, phiên bản case (chuỗi evidence cũ vẫn nhận); chỉ giữ bằng chứng 5 lần chạy gần nhất mỗi case (file cũ bị xoá trên Cloudinary); comment issue có bảng từng bước; có script `python -m app.tools.upload_evidence`; API Kết quả trả đủ thông tin và lọc theo nền tảng/Run/regression; trang Kết quả có bộ lọc và bảng chi tiết bên phải. Backend 503 test, frontend 145 test qua. Chưa thử với Cloudinary/GitHub thật. **Đợt 6 xong** (Task 21–22; 2026-11-17): Màn hình có ô "Dev phụ trách" (tên GitHub, tự bỏ `@`, sai tên thì 422); khi Codex báo FAIL, issue được giao cho dev đó, có nhãn `bug: cần sửa` và dòng `Giao cho @dev` (gán lỗi thì comment cảnh báo, kết quả vẫn ghi; PASS gỡ nhãn bug, giữ người được giao). Backend 520 test, frontend 149 test qua. Chưa thử với GitHub thật. **Đợt 7 xong** (Task 23–25; 2026-11-17): QA Lead/Admin bấm "Chạy bộ regression" ở trang Kết quả, nhập bản build → app tạo run RUNNING gom các case regression đã duyệt, gắn `needs-rerun` kèm "Mã lần chạy" lên từng issue; Codex gửi kết quả kèm `run_id` (có thể gửi nhiều đợt, run tự COMPLETED khi đủ case, hoặc bấm "Kết thúc"); kết quả hiện ngay khi run còn chạy. Run regression không chặn và không bị chặn bởi run thường. Có thêm `GET regression-runs` (liệt kê run đang mở, ngoài plan, để hiện nút Kết thúc sau khi tải lại trang). `add_results` tự ghi kết quả (không nhận hàm `all_case_ids_done` như plan). Backend 543 test, frontend 156 test qua. Chưa thử với GitHub/Codex thật. **Đợt 8 – Task 26 xong** (2026-11-17): `docs/codex-agent.md` viết lại cho hai máy (Windows: web + Android; Mac: iOS), có cách cài, quay video, upload bằng chứng, hai prompt và quy tắc một phiên Codex mỗi máy; `.env.example` đã có sẵn ba biến `CLOUDINARY_*`. Còn **Task 27** (chạy thử thật trên `hieupt-ht/ShopHub`) cần chủ dự án điền `CLOUDINARY_*` vào `.env` và cùng làm.
- Lưu ý: `Sheet` thiếu cột giờ được **tự thêm** thay vì báo lỗi (hai test cũ đã đổi theo). `.venv` của backend đã được dựng lại bằng `uv sync` vì bản cũ trỏ tới miniconda không còn.

## Đang làm (2026-11-18): thêm Google Drive làm nơi lưu ảnh/video

Thiết kế `docs/superpowers/specs/2026-11-18-google-drive-media-design.md`, kế hoạch `docs/superpowers/plans/2026-11-18-google-drive-media.md` (11 task / 3 đợt). Admin chọn nơi lưu (Cloudinary hoặc Drive) cho **từng dự án**; mỗi dự án có thư mục riêng, tự tạo. Cloudinary vẫn giữ nguyên. **Làm từng đợt, xong thì dừng cho chủ dự án `/compact`.**

- **Đợt 1 xong** (Task 1–6, backend; 2026-11-18): `Project.storage` (cột `storage` cuối tab Projects, ô trống = cloudinary, chỉ Admin đổi qua PATCH, chọn drive khi chưa cấu hình thì 422); `Media` nhận cả link `drive.google.com/file/d/<ID>/view` (`ensure_own_media`, `provider_of`, `display_url`, `thumbnail_url`); `DriveClient` (OAuth refresh token, tự tạo thư mục `ai-test-runner/<mã dự án>/<guide|evidence>`, tải lên kiểu resumable, chia sẻ "ai có link", xoá theo ID); `MediaJanitor` xoá đúng nơi; endpoint `POST /api/projects/{id}/media/upload`, `POST /api/agent/projects/{id}/media/upload`, `GET .../media/storage`, `/sign` trả 409 nếu dự án lưu ở Drive; script `python -m app.tools.drive_auth` lấy refresh token; biến `.env` mới `GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN`, `GOOGLE_DRIVE_ROOT_FOLDER_ID`. Backend **656 test** qua, `mypy`, `ruff` sạch. Chưa thử với Google Drive thật.
- **Đợt 2 xong** (Task 7–9, frontend; 2026-11-18): `lib/media/display.ts` (`isDrive`, `displayUrl`, `embedUrl`), `uploadMedia` có tuỳ chọn `storage` (Drive: gửi multipart tới backend, 413/415 → báo đúng lỗi), `MediaPicker`/`MediaLightbox`/chi tiết kết quả hiện ảnh Drive bằng thumbnail và video Drive bằng iframe (`MediaVideo`), `CaseForm` lấy `storage` từ `useProject` truyền xuống ô chọn ảnh, trang Admin có cột "Nơi lưu ảnh/video" (ô chọn; backend từ chối thì hiện lỗi và quay về giá trị cũ). Frontend **190 test** qua, typecheck + lint sạch. Chưa thử trình duyệt thật. Các commit chỉ chứa phần của mình; phần sửa dở của chủ dự án trong `media-picker`, `case-form`, `admin/projects/page.tsx`, `vi.json`, `SETUP.md` vẫn chưa commit.
- **Đợt 3 xong** (Task 10–11; 2026-11-18): script `upload_evidence` tự hỏi `GET .../media/storage` rồi chọn luồng (Cloudinary ký chữ ký; Drive gửi multipart cho app), lỗi 503/502/413/415 báo tiếng Việt, không lộ token; có phụ lục "Bật Google Drive" ở cuối `SETUP.md`, quyết định 40 trong `DECISIONS.md`, `docs/codex-agent.md` cập nhật. Backend **660 test** qua.
- **Còn lại:** thử với Google Drive thật (cần chủ dự án lấy refresh token), review cả nhánh, quyết định merge/PR.
- Lưu ý: cây làm việc đang có thay đổi chưa commit của chủ dự án ở `SETUP.md`, trang admin/projects, `media-picker`, `case-form`, `create-project-dialog`, `vi.json` — sửa chồng lên, không ghi đè, chỉ stage phần của mình.

## Đang làm (2026-11-18): thùng rác dự án

Thiết kế `docs/superpowers/specs/2026-11-18-project-trash-design.md`, kế hoạch `docs/superpowers/plans/2026-11-18-project-trash.md` (3 task, 1 đợt).

- **Đợt thùng rác xong** (Task 1–3): `DELETE /api/projects/{id}` (chỉ Admin, dự án phải đã lưu trữ, body `{name}` gõ đúng tên; 409 chưa lưu trữ, 422 sai tên; xoá thành viên rồi dòng dự án, ghi AuditLog; không đụng Sheet riêng/GitHub/ảnh). Trang Admin → Dự án có 2 tab Đang dùng/Thùng rác, nút Chuyển vào thùng rác, Khôi phục, Xoá vĩnh viễn (gõ tên). Backend **683 test**, frontend **212 test** qua, mypy/ruff/typecheck/lint sạch. Chưa thử trình duyệt thật.
- **Còn lại:** review cả nhánh; sau đó viết plan test tay từ spec `2026-11-18-manual-test-run-design.md`.

## Đang làm (2026-11-18): test tay (Manual)

Thiết kế `docs/superpowers/specs/2026-11-18-manual-test-run-design.md`, kế hoạch `docs/superpowers/plans/2026-11-18-manual-test-run.md` (7 task / 2 đợt, Native, từng đợt).

- **Đợt 1 backend xong** (Task 1–4): trường `execution_mode` (mặc định MANUAL; ô trống ở Sheet cũ = AUTOMATION); case Manual không gửi duyệt, `mark_tested` đưa DRAFT→TESTED, sửa/đổi cách chạy thì về Nháp; `POST /api/projects/{pid}/test-cases/{cid}/manual-results` tạo Run + Result, báo người liên quan, tạo/cập nhật issue (nhãn `mode: manual`, ghi tên người chạy); tester được ký/tải ảnh vào thư mục `evidence`; `last_result` ở chi tiết case; agent và regression bỏ qua case Manual. Backend **727 test**, mypy/ruff sạch.
- **Đợt 2 frontend xong** (Task 5–7, commit `26a95bc`, `b554e05`, `04a738d`): form có hai nút Test tay/Tự động (mặc định Test tay, case Manual không có nút gửi duyệt); danh sách có cột + bộ lọc "Cách chạy" và nhãn "Đã kiểm thử · Pass/Fail" (một request `useResults`, không gọi mỗi dòng); `ManualRunPanel` (kết quả từng bước, ảnh/video bằng chứng, bước lỗi, giao cho dev, nhớ Môi trường); `MediaPicker`/`uploadMedia` nhận `purpose`; trang case hiện khung cho case Manual (Nháp/Đã kiểm thử, có quyền sửa, dự án chưa lưu trữ) và dòng "Lần chạy gần nhất". Frontend **269 test**, typecheck + lint sạch (test hay quá 5 giây khi máy nặng: chạy lại với `--testTimeout=30000`).
- **Còn lại:** review cả nhánh (reviewer mới, kèm Review Focus của plan). Chưa thử trình duyệt thật.

## Đang làm (2026-11-18): ảnh/video cho màn hình + trang chi tiết màn hình

Thiết kế `docs/superpowers/specs/2026-11-18-screen-media-and-detail-design.md`, kế hoạch `docs/superpowers/plans/2026-11-18-screen-media-and-detail.md` (5 task / 2 đợt, làm kiểu Native trong một phiên). Giữ nguyên luật: chỉ Admin/QA Lead tạo-sửa-xoá màn hình; tester chỉ viết case trên màn hình được giao nhưng xem được mọi màn hình.

- **Đợt 1 xong** (Task 1–2, backend): `Screen.media` (cột `media_json` cuối tab Screens, Sheet cũ đọc ra rỗng), API tạo/sửa nhận `media` (link sai kho → 422, tối đa 5), bỏ ảnh khỏi màn hình hoặc xoá màn hình thì `MediaJanitor` xoá file; PATCH không gửi `media` thì giữ nguyên. Backend **669 test** qua, mypy/ruff sạch.
- **Đợt 2 xong** (Task 3–5, frontend): `ScreenFormDialog` có `MediaPicker` (khoá Lưu khi đang tải, dialog rộng hơn + cuộn), `ScreenMediaStrip`, trang `screens/[screenId]` (thông tin, ảnh/video, bảng case của màn hình, nút Sửa/Tạo case theo quyền, không tìm thấy → báo + link về), tên màn hình ở danh sách thành link, `CaseForm` hiện ảnh của màn hình đã chọn và nhắc "nhờ QA Lead giao việc" khi trống. Frontend **203 test** qua, typecheck + lint sạch. Chưa thử trình duyệt thật (1366×768).
- **Còn lại:** review cả nhánh (reviewer mới). Sau đó brainstorm việc 3 (Manual/Automation).
- Lưu ý: không chạy `ruff format` cả thư mục (nó sửa nhầm 40+ file); chỉ `ruff check`.

## Đã xong (2026-11-17): đăng nhập bằng email + mật khẩu

Thay hẳn Google OAuth. Thiết kế `docs/superpowers/specs/2026-11-17-password-login-design.md`, kế hoạch `docs/superpowers/plans/2026-11-17-password-login.md` (12 task / 4 đợt, đã làm hết).

- Backend: mật khẩu băm argon2, cột `password_hash` ở tab Users (không bao giờ trả ra API), `POST /api/auth/login`, khoá 5 lần sai / 15 phút, `POST /api/auth/change-password`, `POST /api/users/{email}/reset-password` (xoá mọi phiên cũ). Admin đầu tiên lấy từ `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD`; Admin cũ chưa có hash sẽ được đặt hash ở lần khởi động đầu. Đã gỡ Google OAuth và authlib. Service Account và Sheet riêng tư giữ nguyên.
- Frontend: trang đăng nhập email + mật khẩu, form tạo user có ô mật khẩu, nút chìa khoá "Đặt lại mật khẩu" ở mỗi dòng, mục "Đổi mật khẩu" trong menu người dùng ở thanh trên.
- Tài liệu (`SETUP.md`, `README.md`, `docs/architecture.md`, `.env.example`) đã đổi sang mật khẩu.
- Kiểm tra cuối: backend 604 test qua, mypy và ruff sạch; frontend 175 test qua, typecheck và lint sạch.
- Chưa làm: thử bằng trình duyệt thật; review toàn nhánh; quyết định merge/PR (chờ chủ dự án).

## Việc còn dở

1. Luồng end-to-end (duyệt case → issue → Codex chạy → API → app comment, đổi nhãn) và luồng Chạy lại đã chạy được trên `hieupt-ht/ShopHub`. Còn cần đối chiếu thêm tab `Results` và thông báo hoàn tất, và thử trường hợp PASS.
2. ~~Ảnh bằng chứng~~ Đã xong bằng Cloudinary (script `app.tools.upload_evidence`); chỉ còn chờ chạy thử thật (Task 27).
3. Kiểm tra giao diện bằng mắt ở trình duyệt thật, đặc biệt hộp thoại, chuông thông báo, các tab "Việc của tôi", trang Kết quả và Tổng quan trên màn hình hẹp. Test tự động frontend đã qua nhưng chưa thay thế kiểm tra này.

## Công nghệ và lệnh kiểm tra

- Backend: Python 3.12, FastAPI, Redis, Google Sheets, GitHub App; thư mục `backend/`, quản lý bằng `uv`.
- Frontend: Next.js 16, TypeScript, Tailwind, next-intl; thư mục `frontend/`. Đọc `frontend/AGENTS.md` và tài liệu trong `frontend/node_modules/next/dist/docs/` trước khi viết route.
- Backend: `cd backend && uv run pytest -q && uv run mypy app && uv run ruff check`.
- Frontend: `cd frontend && npx vitest run && npm run typecheck && npm run lint`.
- Khi sửa API: `cd frontend && npm run gen:api`.

## Quy ước không được quên

- Chủ dự án là sinh viên đang học: giải thích bằng **tiếng Việt đơn giản**, code dễ đọc, comment tiếng Việt.
- TDD: viết test, xem đỏ, rồi mới sửa code. Chạy cả hai bộ test trước khi báo xong.
- Không commit thẳng vào `main`. Commit theo Conventional Commits: type tiếng Anh, mô tả tiếng Việt có dấu. Trên Windows dùng heredoc Git Bash cho message. Không push, không tạo PR khi chưa được đồng ý.
- Không in hay commit giá trị trong `.env`, `worker-projects.json`. `AGENT_API_TOKEN` chỉ ở `.env`/môi trường, không đưa vào Sheet, log hay response.
- Chỉ backend ghi Sheet, qua repository; chỉ `gateway.py` gọi Google. Lỗi API có `{"detail": "<câu tiếng Việt>"}`. Chuỗi giao diện đặt ở `frontend/messages/vi.json`.
- Mã case `TC-000001` có thể trùng giữa các dự án: mọi khoá dùng chung và mọi tìm kiếm issue phải kèm dự án hoặc repo.
- Google Sheets có hạn mức đọc khoảng 60 lần/phút; tránh thêm lượt đọc dày. Issue của repo công khai không được chứa `test_data` hay email người tạo/sửa.

## Sửa theo review cả nhánh `feature/fun-ui`
Reviewer: không có lỗi nghiêm trọng. Đã sửa (đều viết test đỏ trước):
- Màu nút chính Kẹo ngọt `--primary` / `--sidebar-primary` đổi `#B15CFF` → `#8F3FE0` (chữ trắng đạt ~5.3:1). `#B15CFF` còn dùng cho `--ring`, `--accent`, đồ thị.
- Bảng xếp hạng trống hiện câu mời thay vì dòng "Chưa có điểm".
- Trang Tổng quan project báo lỗi khi API lỗi (không hiện khung chờ mãi).
- Nút nhạc theo sự kiện `play`/`pause` của thẻ audio (nhạc dừng từ bên ngoài).
- Chuỗi ngày của nhím dùng chữ `sr-only` thay `aria-label` trên thẻ `p`.
- `from_iso` coi giờ thiếu múi giờ là UTC (tránh lỗi 500 khi Sheet bị sửa tay).
Chưa sửa (nhỏ, để sau): thanh lên cấp tính từ 0 bug; chữ phụ trên nền `--muted` hơi nhạt; `/me/pet` và `/me/dashboard` đọc Sheet 2 lần ở lần đầu; mã màu riêng của nhím ngoài danh sách ngoại lệ; thiếu test 404 cho `/leaderboard`.

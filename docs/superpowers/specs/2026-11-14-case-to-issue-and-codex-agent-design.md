# Test case vào cả GitHub issue và Google Sheets, Codex agent đọc issue để chạy test (thiết kế)

Ngày: 2026-11-14 · Trạng thái: **chờ chủ dự án duyệt** (chưa duyệt thì chưa viết kế hoạch, chưa code) · Nhánh: `feature/ai-agent-runner` (tách từ `develop`)

Nhãn: **[Chủ dự án]** = chủ dự án đã chốt; **[Đề xuất]** = người viết tài liệu đề xuất, chủ dự án chưa xác nhận.

## 1. Mục đích

Chủ dự án muốn test case của tester **vừa nằm ở Google Sheets, vừa thành một GitHub issue**, để một **AI agent có terminal (Codex)** đọc case từ issue qua **GitHub MCP**, tự viết và chạy kịch bản Playwright, rồi báo kết quả. **[Chủ dự án]**

Vì sao: hướng worker Playwright tự viết sẵn (nhánh `feature/m4-playwright-worker`, tag `m4-playwright-v1`) bắt tester điền từng bước tự động. Chủ dự án muốn AI đọc case viết bằng chữ thường và tự lo phần kịch bản. Hướng Playwright được **giữ nguyên làm bản lưu**, không bỏ.

## 2. Mục tiêu / không phải mục tiêu

Mục tiêu:
- Tester tạo hoặc sửa case trên web → case vẫn lưu vào Sheet như hiện nay, **và** có một issue tương ứng ở repo GitHub của dự án.
- Codex đọc các issue case (qua GitHub MCP), chạy test, rồi **comment kết quả** lên đúng issue đó.
- Kết quả PASS/FAIL lấy từ **mã thoát và báo cáo JSON của Playwright**, không lấy từ lời Codex nói. **[Đề xuất]**

Không làm:
- Không bỏ Sheet: Sheet vẫn là **nơi lưu chính** và là nguồn đúng khi hai bên khác nhau. **[Đề xuất]**
- Không chạy test bên trong ứng dụng web này; web chỉ quản lý case.
- Chưa mang code worker Playwright sang nhánh này (có thể lấy lại từ tag `m4-playwright-v1` nếu cần).

Điều phải tránh: một issue mất đồng bộ làm Codex chạy nhầm bản case cũ; lộ mật khẩu hay dữ liệu nhạy cảm trong `test_data` ra issue của repo công khai.

## 3. Các hướng đã cân nhắc

| Hướng | Mô tả | Đánh đổi |
|---|---|---|
| **A. Sheet là nguồn chính, issue là bản sao một chiều (đề xuất)** | Web ghi Sheet trước, rồi tạo/cập nhật issue từ dữ liệu đó | Một nguồn đúng, issue hỏng vẫn không mất case. Phải đồng bộ một chiều |
| B. Issue là nơi lưu chính, Sheet là bản sao | Ngược lại | Bị giới hạn lượt gọi GitHub, mất tính năng xung đột version đang chạy tốt trên Sheet. Chủ dự án không chọn |
| C. Codex đọc thẳng từ API/MCP của chính ai-test-runner, issue chỉ để theo dõi | Không cần issue làm nơi giao việc | Đơn giản nhất, nhưng chủ dự án muốn dùng issue |

**[Chủ dự án]** chọn có cả issue và Sheet; **[Đề xuất]** làm theo hướng A.

## 4. Thiết kế đề xuất

### 4.1 Đồng bộ case → issue (backend)
- Khi case được **tạo, sửa nội dung, duyệt, trả lại, ngừng dùng (`DEPRECATED`), khôi phục**, backend cập nhật issue của case đó. Sau khi **đã ghi Sheet thành công**.
- Một case = một issue, tạo ở **repo của dự án** (`repo_full_name`, repo của app đang test) **[Chủ dự án]**. Tìm issue bằng **label `tc:TC-000123`** (đã có trong spec gốc mục 7.9, chống trùng), nên **không thêm cột vào Sheet** và case cũ vẫn dùng được. Tạo label nếu chưa có. Tiêu đề `[TC-000123] <tiêu đề case>`.
- Thân issue: màn hình, mức độ, ưu tiên, điều kiện, các bước (có kết quả mong đợi từng bước), kết quả mong đợi, trạng thái case. Thêm label trạng thái (`status:APPROVED`...) để Codex lọc case đã duyệt.
- `DEPRECATED` → đóng issue; khôi phục → mở lại.
- **Lỗi GitHub không được làm hỏng việc lưu case** (giống quyết định 24): Sheet đã ghi thì trả thành công, ghi log, và có thao tác **"Đồng bộ lại issue"** (idempotent nhờ label) cho QA Lead/Admin. **[Đề xuất]**
- GitHub App đã có quyền `Issues: Read and write` theo README mục 4; thêm `GitHubClient` các hàm tìm/tạo/sửa issue, comment, đóng/mở. Lưu ý lượt gọi GitHub bị giới hạn: đồng bộ chạy nền, không chặn request. **[Đề xuất]**

### 4.2 Codex đọc issue và chạy test (ngoài ứng dụng web)
- Codex dùng **GitHub MCP** để liệt kê issue có label `test-case` và `status:APPROVED`, đọc nội dung.
- Codex đọc repo app đang test, viết kịch bản Playwright cho từng case, chạy `npx playwright test --reporter=json` trong terminal ở **thư mục riêng**, đọc kết quả và ảnh chụp.
- Báo kết quả: **comment lên issue của case** (PASS/FAIL, bước lỗi, đường dẫn ảnh). Kết quả chính thức đến từ báo cáo JSON của Playwright. **[Đề xuất]**
- Quyền terminal chỉ cho vài lệnh cần (`npm run dev`, `npx playwright test`), không đọc `.env`. **[Đề xuất]**

### 4.3 Ghi kết quả về Sheet (cần chủ dự án chốt, xem mục 6)
Dùng lại tab `Runs`/`Results` đã có trong Sheet dự án. Codex ghi qua một API/CLI nhỏ của ai-test-runner (không để Codex tự ghi Sheet). **[Đề xuất]**

## 5. Ràng buộc và rủi ro
- Issue nhìn thấy được bởi mọi người có quyền đọc repo. Trường `test_data` có thể chứa mật khẩu: **mặc định không đưa `test_data` vào issue** (để Codex lấy qua API khi cần). **[Đề xuất]**
- Mỗi case một issue sẽ rất nhiều issue (200 case = 200 issue). Dùng label và lọc; chủ dự án đã chọn cách này. **[Chủ dự án]**
- Codex không tự "nghe" issue mới: cần cách gọi (mục 6).
- Hạn mức GitHub: tạo hàng loạt issue (ví dụ duyệt 100 case cùng lúc) cần xếp hàng và chậm lại, không gọi dồn.
- Hạn mức đọc Google Sheets (~60 lượt/phút) vẫn áp dụng.

## 6. Cần chủ dự án quyết (chặn kế hoạch)

**Đã chốt:** issue nằm ở **chính repo của app đang test** (repo gắn với dự án, lấy từ trường `repo_full_name`). **[Chủ dự án, 2026-11-14]**

Còn 4 câu:
1. **Khi nào tạo issue?** (a) ngay khi tạo case (có cả case nháp), hoặc (b) chỉ khi case được **duyệt**. Đề xuất (b) để issue không bị ngập case nháp; nhưng chủ dự án từng nói "khi tester nhập".
2. **Codex được gọi bằng cách nào?** (a) chủ dự án tự mở Codex và gõ lệnh, hoặc (b) nút trên web làm worker gọi `codex exec`. Đề xuất (a) trước.
3. **Kết quả ghi vào đâu?** Chỉ comment lên issue, hay thêm ghi vào tab `Results` của Sheet. Đề xuất cả hai.
4. **Repo của app test là công khai hay riêng tư?** Quyết định có đưa `test_data` vào issue hay không.

## 7. Phạm vi việc cho người làm (để lập kế hoạch sau khi duyệt)
1. `GitHubClient`: tìm/tạo/sửa/đóng-mở issue, tạo label, comment (kèm test với bản giả, theo mẫu `FakeGitHub`).
2. Dịch vụ đồng bộ case → issue (idempotent bằng label), chạy nền, không làm hỏng việc lưu case; thao tác "Đồng bộ lại".
3. Gắn đồng bộ vào các thao tác case hiện có (tạo, sửa, duyệt hàng loạt, trả lại, ngừng dùng, khôi phục).
4. (Nếu chọn ghi Sheet) API/CLI cho Codex ghi `Runs`/`Results`.
5. Tài liệu hướng dẫn cấu hình Codex: GitHub MCP, quyền terminal, prompt mẫu.
6. Tuỳ chọn: lấy lại phần cần từ `m4-playwright-v1` (Runs/Results, tab Chạy test).

Mọi chi tiết còn lại (tên file, tên hàm, bố cục nội dung issue) để người làm quyết, theo quy ước trong `AGENTS.md`.

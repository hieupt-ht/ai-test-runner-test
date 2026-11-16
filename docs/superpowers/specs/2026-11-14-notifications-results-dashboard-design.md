# Thông báo (chuông), kết quả test và trang chủ có nội dung — thiết kế

Ngày: 2026-11-14. Nhánh: `feature/ai-agent-runner`. Người thực hiện dự kiến: Codex (Claude Code gần hết token).

## 1. Mục đích

Hiện QA/Tester không biết khi nào mình được thêm vào dự án, được giao màn hình, bị trả case, và không thấy kết quả test do agent ghi. Trang Tổng quan và "Việc của tôi" thì trống hoặc thiếu phân loại. Mục tiêu: người dùng mở app là biết **việc gì đang chờ mình** và **kết quả test ra sao**, không phải mở Google Sheet hay GitHub.

## 2. Mục tiêu / không phải mục tiêu / điều phải tránh

**Mục tiêu**
- Chuông thông báo trong app, có đếm chưa đọc, đánh dấu đã đọc.
- Tab **Kết quả** trong dự án: PASS/FAIL/BLOCKED/INCONCLUSIVE kèm lý do, bước lỗi, link issue.
- "Việc của tôi" có tab Đang làm / Đã xong.
- Tổng quan có nội dung theo vai trò.
- Sửa giao diện hộp thoại tạo dự án bị vỡ.

**Không làm**
- Không gửi email, không đẩy thông báo ra ngoài app.
- Không thêm chức năng xoá dự án (chủ dự án chốt: giữ nút **Lưu trữ**, không đổi gì).
- Không xoá issue GitHub khi agent comment xong; issue chỉ được đóng khi case ngừng dùng (đã có sẵn).
- Không mở Google Sheet cho Tester/QA; chỉ Admin mở khi cần.

**Điều phải tránh**
- Chuông làm vượt hạn mức đọc Sheets (~60 lần/phút).
- Thông báo lỗi làm hỏng thao tác chính (ghi case, duyệt…): gửi thông báo là "cố gắng hết sức", lỗi chỉ ghi log.
- Lộ `test_data`, email người tạo/sửa ra issue công khai (đã có quy ước).

## 3. Các cách đã cân nhắc cho chuông (chủ dự án chọn A)

| Cách | Nhận xét |
|---|---|
| **A. Redis (chọn)** | Redis đã dùng sẵn; đọc nhanh, không tốn hạn mức Sheets. Mất thông báo cũ không hại dữ liệu chính. |
| B. Tab Notifications trong Sheet | Bền nhưng mỗi lần tải chuông tốn một lần đọc Sheet, dễ vượt hạn mức. |
| C. Suy ra từ audit log | Không có trạng thái đã đọc, thiếu sự kiện. |

## 4. Thiết kế

### 4.1 Thông báo (Redis)
- Mỗi người dùng một danh sách theo email đã chuẩn hoá. Mỗi thông báo: `id`, `type`, `title` (tiếng Việt), `link` (đường dẫn trong app), `created_at`, `read`.
- Giữ tối đa 100 thông báo gần nhất mỗi người, hết hạn sau 30 ngày.
- API: `GET /api/notifications` (danh sách + số chưa đọc), `POST /api/notifications/{id}/read`, `POST /api/notifications/read-all`. Chỉ đọc thông báo của chính mình.
- Giao diện: biểu tượng chuông trên thanh đầu trang, huy hiệu số chưa đọc, danh sách thả xuống. Hỏi lại số chưa đọc mỗi 45 giây khi tab đang mở.
- Sự kiện phát ra thông báo (gọi từ service, bọc try/except, lỗi chỉ ghi log):
  1. Được thêm vào dự án → người được thêm.
  2. Được giao màn hình → người được giao.
  3. Case bị trả lại → người tạo case (kèm nhận xét).
  4. Case được duyệt → người tạo case.
  5. Agent ghi xong kết quả → QA Lead/Admin của dự án và người tạo từng case FAIL.
- Thông báo không chứa dữ liệu nhạy cảm (không `test_data`, không mật khẩu).

### 4.2 Tab Kết quả
- Backend: thêm API đọc `Results`/`Runs` theo dự án (đã có `RunRepository`, `ResultRepository.list_for_run`; cần kiểm tra chưa có API đọc cho giao diện). Quyền xem: thành viên dự án; Tester chỉ thấy case của mình, QA Lead/Admin thấy cả dự án.
- Giao diện: tab **Kết quả** trong trang dự án; mỗi dòng là case + huy hiệu trạng thái + lý do + bước lỗi + link issue (tìm bằng label đã có). Có lọc theo trạng thái.
- Chú ý hạn mức đọc Sheet: dùng cache có sẵn (`core/cache.py`) và không đọc lặp trong một request.

### 4.3 "Việc của tôi"
- Hai tab: **Đang làm** (TODO, WRITING, IN_REVIEW) và **Đã xong** (APPROVED, TESTED). Lọc ở frontend từ dữ liệu `useMyAssignments` đã có. Việc xong không bị xoá.

### 4.4 Tổng quan (theo vai trò)
- Tester: việc đang làm, việc sắp hết hạn, case bị trả lại.
- QA Lead: case chờ duyệt, kết quả test gần nhất, việc quá hạn.
- Admin: số dự án, số người dùng, kết quả test gần nhất.
- Phần chưa có dữ liệu hiển thị trạng thái trống rõ ràng, không để màn hình trắng.

### 4.5 Sửa nhanh
- Hộp thoại tạo dự án ([create-project-dialog.tsx](../../../frontend/components/projects/create-project-dialog.tsx)) bị vỡ bố cục: **chưa biết nguyên nhân**, cần mở bằng trình duyệt thật để xem (xem mục 6).

## 5. Thứ tự làm (mỗi bước một nhóm commit, TDD)

1. **Nhóm A** — sửa hộp thoại tạo dự án.
2. **Nhóm B1** — hạ tầng thông báo: kho Redis, API, chuông trên giao diện.
3. **Nhóm B2** — phát thông báo từ 5 sự kiện ở 4.1.
4. **Nhóm B3** — API đọc kết quả và tab Kết quả.
5. **Nhóm C** — tab Đang làm/Đã xong và Tổng quan theo vai trò.

## 6. Việc để người xây tự quyết hoặc cần xem tận mắt
- Nguyên nhân giao diện vỡ ở hộp thoại tạo dự án (cần chạy `npm run dev` và xem bằng mắt, kể cả màn hình hẹp).
- Chi tiết khoá Redis, tên khoá, cách đếm chưa đọc nhanh nhất.
- Thiết kế hiển thị chi tiết (màu huy hiệu dùng lại `StatusBadge` nếu phù hợp).
- Chuỗi giao diện đặt trong `frontend/messages/vi.json`; sửa API xong chạy `npm run gen:api`.
- Cách lấy link issue cho từng case trong tab Kết quả mà không gọi GitHub dồn dập (ưu tiên lưu `evidence` do agent gửi, hoặc tìm theo label có chặn số lần).

## 7. Quy ước bắt buộc (nhắc lại)
Tiếng Việt đơn giản, comment tiếng Việt; không push/PR khi chưa được đồng ý; commit theo Conventional Commits; chạy cả hai bộ test (`uv run pytest -q && uv run mypy app && uv run ruff check`, `npx vitest run && npm run typecheck && npm run lint`) trước khi báo xong; không in giá trị `.env`.

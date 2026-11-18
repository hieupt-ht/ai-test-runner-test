# Ảnh/video cho màn hình và trang chi tiết màn hình — thiết kế ngắn

Ngày: 2026-11-18. Đã được chủ dự án duyệt trong cuộc trao đổi.

## Vì sao

Tester cần **hình dung đúng màn hình** trước khi viết test case. Hiện màn hình chỉ có tên, mô tả, route nên tester dễ viết case lệch. Ngoài ra tester bấm vào màn hình muốn thấy ngay danh sách case của màn hình đó.

Lỗi "tester bấm ô chọn màn hình không thấy gì" **không phải lỗi code**: tester chỉ được tạo case trên màn hình được giao (`selectableScreens` + backend 403). Chủ dự án quyết định **giữ luật này**; chỉ cần nói rõ cho người dùng khi danh sách trống.

## Mục tiêu

- Admin / QA Lead gắn ảnh, video cho màn hình khi tạo/sửa (tải lên, kéo thả, dán), giống `MediaPicker` ở test case.
- Trang chi tiết màn hình: thông tin + ảnh/video + bảng test case của màn hình.
- Form tạo case hiện ảnh của màn hình vừa chọn.

## Không làm

- Không cho tester tạo/sửa/xoá màn hình (giữ `MANAGE_SCREENS` = Admin, QA Lead).
- Không bỏ luật "tester chỉ tạo case trên màn hình được giao".
- Không đưa ảnh màn hình lên GitHub issue: ảnh chỉ để tester tham khảo trong app. Ảnh hướng dẫn trong bước và bằng chứng khi fail đã có đường riêng tới Codex/dev.
- Phần Manual/Automation (việc 3) bàn riêng sau.

## Cách làm đã cân nhắc

- **A. Trang riêng `/projects/<id>/screens/<screenId>`** — có link riêng để gửi, đủ chỗ cho ảnh và bảng, có nút "Tạo case" điền sẵn màn hình. Tốn thêm một route. **Đã chọn.**
- B. Bảng trượt bên phải trên trang Màn hình (như trang Kết quả) — không chuyển trang nhưng chật cho ảnh lớn và bảng dài, không có link riêng.
- C. Giữ link sang trang Test case đã lọc, thêm khung ảnh màn hình ở đầu — ít code nhất nhưng trang Test case gánh thêm việc, dễ rối.

## Thiết kế

**Backend**
- `Screen` có thêm trường `media: MediaList` (mặc định rỗng). Tab `Screens` thêm cột `media_json` ở **cuối** `SCREEN_COLUMNS` (Sheet cũ tự thêm cột lúc khởi động như các lần trước).
- `CreateScreenRequest` / `UpdateScreenRequest` nhận `media`. Kiểm tra link thuộc đúng nơi lưu của dự án (`ensure_own_media`, như test case).
- Sửa màn hình mà bỏ bớt ảnh → ảnh bị bỏ được xoá qua `MediaJanitor`. Xoá màn hình (chỉ được khi không còn case/giao việc) → xoá luôn ảnh của nó.
- Upload dùng luồng có sẵn (`/media/sign` cho Cloudinary, `/media/upload` cho Drive), thư mục `guide`.
- Không thêm endpoint đọc mới: trang chi tiết dùng `GET screens` và `GET test-cases` đã có (tránh thêm lượt đọc Sheet).

**Frontend**
- `ScreenFormDialog` thêm `MediaPicker` (truyền `storage` của dự án).
- Route mới `app/(app)/projects/[projectId]/screens/[screenId]/page.tsx` (đọc `frontend/AGENTS.md` và docs Next 16 trước khi viết):
  - Mọi thành viên xem được. Nút Sửa chỉ khi có `MANAGE_SCREENS` và dự án chưa lưu trữ.
  - Thông tin màn hình (mã, tên, mô tả, route, dev phụ trách), ảnh/video (bấm phóng to bằng `MediaLightbox`).
  - Bảng case của màn hình: mã, tiêu đề, trạng thái, mức độ, nền tảng; bấm dòng mở case.
  - Nút "Tạo case" → `test-cases/new?screen=<id>`, chỉ hiện khi người dùng tạo được case trên màn hình này (dùng `selectableScreens`).
  - Không tìm thấy màn hình → thông báo "Không tìm thấy màn hình" + link quay lại.
- Bảng ở tab Màn hình: tên màn hình thành link tới trang chi tiết.
- `CaseForm`: chọn màn hình xong hiện hàng ảnh nhỏ của màn hình đó (bấm phóng to). Danh sách màn hình trống → câu "Bạn chưa được giao màn hình nào, hãy nhờ QA Lead giao việc".
- Chuỗi giao diện đặt ở `messages/vi.json`.

**Test (TDD)**
- Backend: đọc/ghi cột `media_json`, Sheet cũ không có cột vẫn đọc được (rỗng), API nhận `media`, link sai nơi lưu → 422, bỏ ảnh → janitor được gọi, tester vẫn bị 403 khi tạo/sửa màn hình.
- Frontend: trang chi tiết (hiện case đúng màn hình, nút Sửa/Tạo case theo quyền, không tìm thấy), link tên màn hình, form màn hình gửi `media`, `CaseForm` hiện ảnh màn hình và câu báo khi trống.

## Để người làm tự quyết

- Bố cục chi tiết, kích thước ảnh nhỏ, cách sắp xếp bảng case (mặc định theo mã case).
- Có tách component bảng case dùng chung với trang Test case hay không.

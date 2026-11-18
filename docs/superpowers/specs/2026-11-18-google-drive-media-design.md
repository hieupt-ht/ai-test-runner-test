# Thiết kế: thêm Google Drive làm nơi lưu ảnh/video (song song với Cloudinary)

Ngày: 2026-11-18 · Trạng thái: chủ dự án bảo "làm đi" (bỏ qua bước duyệt riêng)

## Mục đích

Chủ dự án muốn lưu ảnh/video (hướng dẫn trong case và bằng chứng của agent) trên Google Drive cá nhân (Gmail),
nhưng **chưa bỏ Cloudinary**. Admin chọn nơi lưu cho từng project. Trên cả hai nơi, mỗi project có thư mục riêng
và thư mục được **tự tạo**, không tạo tay. Sheet vẫn chỉ giữ link.

## Mục tiêu / không phải mục tiêu

- Mục tiêu: tester và Codex tải ảnh/video lên nơi lưu của project; xem lại được; xoá khi không còn dùng.
- Không làm: di chuyển file cũ giữa hai nơi; Shared Drive/Workspace; phân quyền xem từng người.
- Chấp nhận: video lưu ở Drive chỉ có 1 ảnh đại diện trong issue GitHub (Cloudinary vẫn có 6 ảnh cắt).

## Các hướng đã cân nhắc

1. **Mỗi nơi lưu là một "provider", project chọn provider (chọn).** Giao diện chung: tạo yêu cầu upload, xoá, link hiển thị.
2. Công tắc toàn app. Đơn giản hơn nhưng không linh hoạt; chủ dự án đang nghĩ theo project.
3. Bỏ hẳn Cloudinary. Chủ dự án nói chưa cần.

## Thiết kế đã chốt

**Chọn nơi lưu:** thêm trường `storage` (`cloudinary` | `drive`) cho project, Admin sửa ở trang `admin/projects`.
Project cũ mặc định `cloudinary`. Provider chưa cấu hình trong `.env` thì không cho chọn / trả 503 "Chưa cấu hình ...".

**Thư mục theo project (tự tạo):**
- Cloudinary: giữ `ai-test-runner/<mã project>/<guide|evidence>` (Cloudinary tự tạo khi có file đầu tiên).
- Drive: backend tìm hoặc tạo `<thư mục gốc>/<mã project>/<guide|evidence>` bằng API, nhớ ID thư mục trong bộ nhớ
  để lần sau khỏi tìm lại.

**Drive, xác thực:** Gmail cá nhân không cho service account chứa file, nên dùng OAuth một lần
(phạm vi `drive.file`), lấy `refresh token`. Biến `.env` mới: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
`GOOGLE_OAUTH_REFRESH_TOKEN`, `GOOGLE_DRIVE_ROOT_FOLDER_ID` (tuỳ chọn). Script nhỏ giúp lấy refresh token.

**Tải lên:**
- Cloudinary: giữ luồng ký chữ ký, trình duyệt/Codex tải thẳng (`/media/sign`).
- Drive: trình duyệt/Codex gửi `multipart` tới backend (`POST .../media/upload`), backend đẩy lên Drive, đặt quyền
  "ai có link đều xem", trả về `Media`. Kiểm tra loại file và dung lượng (ảnh ≤ 10MB, video ≤ 100MB).
- Endpoint `sign` hiện có trả thêm cho client biết dùng luồng nào (`provider`), để frontend và script Codex rẽ nhánh.

**Dữ liệu `Media`:** nhận ra nơi lưu từ link: `res.cloudinary.com/...` hoặc `drive.google.com/file/d/<ID>/view`
(`public_id` = ID file Drive). Bộ kiểm tra link nhận cả hai; với Drive, kiểm tra ID thuộc thư mục của app khi ghi.

**Hiển thị:** một hàm trung tâm ở frontend đổi `Media` thành link hiển thị: Cloudinary như cũ; Drive dùng
`drive.google.com/thumbnail?id=<ID>&sz=w1600` cho ảnh và `drive.google.com/file/d/<ID>/preview` (iframe) cho video.

**Xoá file:** `MediaJanitor` chọn đúng provider theo link của từng file (Cloudinary `destroy`, Drive `files.delete`).

**Issue GitHub:** `frames.py` chỉ chạy cho link Cloudinary; video Drive chỉ có link và ảnh đại diện.

## Việc để người làm quyết

- Dùng `httpx` gọi thẳng API Drive hay thư viện Google; nên dùng upload "resumable" cho video lớn.
- Cách cache access token; vị trí lưu cột `storage` trong Sheet project.
- Cập nhật `SETUP.md`, `.env.example`, `docs/codex-agent.md`, `HANDOFF.md`, `DECISIONS.md`.

## Cách làm việc

Theo AGENTS.md: TDD (test đỏ trước), chạy cả hai bộ test, commit nhỏ trên nhánh hiện tại, không push khi chưa được đồng ý.
Làm theo từng đợt (backend → frontend → script Codex → tài liệu), ghi tiến độ vào plan và HANDOFF.

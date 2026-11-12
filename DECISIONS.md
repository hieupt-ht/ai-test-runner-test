# Các quyết định và giả định

Ghi lại những chỗ tài liệu thiết kế chưa nói rõ và cách đã chọn. Mục mới thêm vào cuối file.

1. **Backend viết đồng bộ (sync), endpoint khai báo bằng `def`.** FastAPI tự chạy các hàm này trong threadpool. Thư viện Google Sheets vốn đồng bộ, nên viết sync giúp code đơn giản và dễ đọc hơn async.

# Các quyết định và giả định

Ghi lại những chỗ tài liệu thiết kế chưa nói rõ và cách đã chọn. Mục mới thêm vào cuối file.

1. **Backend viết đồng bộ (sync), endpoint khai báo bằng `def`.** FastAPI tự chạy các hàm này trong threadpool. Thư viện Google Sheets vốn đồng bộ, nên viết sync giúp code đơn giản và dễ đọc hơn async.
2. **Next.js 16.4 bật `cacheComponents`.** next-intl chỉ dùng ở phía client (nạp sẵn `messages/vi.json`), không đọc gì từ request trên server, để không phải bọc `<Suspense>` khắp nơi.
3. **Kiểu TypeScript sinh từ OpenAPI** bằng lệnh `npm run gen:api`. Lệnh này xuất OpenAPI trực tiếp từ code backend, không cần bật server.
4. **Backend chạy bằng `uvicorn app.main:create_app --factory`**, không tạo biến `app` ở cấp module, để import `app.main` trong test không tự đọc cấu hình thật.
5. **Một file `.env` duy nhất ở thư mục gốc**, dùng chung cho Docker và khi chạy backend trực tiếp. Test luôn dùng `Settings(_env_file=None)` để không phụ thuộc cấu hình trên máy.
6. **Bootstrap Admin**: tên hiển thị mặc định là "Admin". Admin đổi lại tên trong trang Người dùng.

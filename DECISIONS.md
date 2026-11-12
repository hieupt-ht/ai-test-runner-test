# Các quyết định và giả định

Ghi lại những chỗ tài liệu thiết kế chưa nói rõ và cách đã chọn. Mục mới thêm vào cuối file.

1. **Backend viết đồng bộ (sync), endpoint khai báo bằng `def`.** FastAPI tự chạy các hàm này trong threadpool. Thư viện Google Sheets vốn đồng bộ, nên viết sync giúp code đơn giản và dễ đọc hơn async.
2. **Next.js 16.4 bật `cacheComponents`.** next-intl chỉ dùng ở phía client (nạp sẵn `messages/vi.json`), không đọc gì từ request trên server, để không phải bọc `<Suspense>` khắp nơi.
3. **Kiểu TypeScript sinh từ OpenAPI** bằng lệnh `npm run gen:api`. Lệnh này xuất OpenAPI trực tiếp từ code backend, không cần bật server.
4. **Backend chạy bằng `uvicorn app.main:create_app --factory`**, không tạo biến `app` ở cấp module, để import `app.main` trong test không tự đọc cấu hình thật.
5. **Một file `.env` duy nhất ở thư mục gốc**, dùng chung cho Docker và khi chạy backend trực tiếp. Test luôn dùng `Settings(_env_file=None)` để không phụ thuộc cấu hình trên máy.
6. **Bootstrap Admin**: tên hiển thị mặc định là "Admin". Admin đổi lại tên trong trang Người dùng.
7. **Người ngoài dự án nhận 404, không phải 403**, để không lộ là dự án đó có tồn tại.
8. **Repo và Google Sheet của dự án không đổi được sau khi tạo.** Đổi repo làm `code_paths` của các màn hình mất ý nghĩa. Branch vẫn đổi được.
9. **Mã dự án `PRJ-0001`** tính bằng số lớn nhất hiện có + 1 (trong khoá của tab `Projects`). Mã màn hình `SC-0001` và việc được giao `AS-0001` lấy từ bộ đếm ở tab `Meta` của Sheet dự án.
10. **Chỉ giao việc cho Tester đang hoạt động trong dự án.** Deadline tính theo giờ Việt Nam và không được ở quá khứ.
11. **Không xoá màn hình đang được giao việc, không bỏ thành viên đang được giao việc.** Phải bỏ giao việc trước.
12. **Trạng thái việc ở M2 luôn là `TODO`.** Từ M3, trạng thái tự suy ra từ các test case.
13. **Một khoá cho cả tab khi ghi** (`lock:system:projects`, `lock:system:project-members`, `lock:<project_id>:screens`, `lock:<project_id>:assignments`), vì thêm hoặc xoá dòng có thể làm các dòng khác dịch chỗ.
14. **Giao diện chưa có nút đổi deadline.** API `PATCH /api/projects/{id}/assignments/{id}` đã có và đã có test; tạm thời đổi deadline bằng cách bỏ giao việc rồi giao lại.

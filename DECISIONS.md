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
15. **Tester chỉ tạo case trên màn hình được giao cho mình; sửa được case mình tạo hoặc case thuộc màn hình được giao.** Bị bỏ giao việc vẫn sửa được case mình tạo.
16. **Trạng thái việc tính theo các case do chính tester đó tạo trên màn hình đó.** Mọi case của tester đều `DEPRECATED` thì coi như `TODO`. M3 chưa có run nên chưa bao giờ ra `TESTED`.
17. **Không đổi `screen_id` của case sau khi tạo.** Mã case `TC-000123` cũng không sửa được.
18. **Mỗi bước của case: `action` bắt buộc, `expected` được để trống.**
19. **Ai có quyền sửa case thì được chuyển case sang `DEPRECATED`; chỉ QA Lead/Admin khôi phục.** Khôi phục đưa case về `DRAFT`.
20. **Không xoá màn hình đang có test case**, kể cả case đã `DEPRECATED`.
21. **Mọi thao tác chuyển trạng thái cũng gửi `version` và cũng bị kiểm tra xung đột.** Nhờ vậy QA Lead không duyệt nhầm một nội dung mà mình chưa đọc.
22. **Lọc, tìm, phân trang làm ở trình duyệt.** Tìm không phân biệt hoa thường và dấu tiếng Việt.
23. **Quy tắc khoá khi ghi case.** Tạo case khoá cả tab `lock:<project_id>:test-cases`; sửa case khoá theo bản ghi `lock:<project_id>:test-case:<id>` (tab `TestCases` không xoá dòng nên dòng không dịch chỗ). Khi lồng khoá, luôn lấy `assignments` trước rồi mới `test-cases`, không bao giờ ngược lại.
24. **Cập nhật trạng thái việc sau khi lưu case là "cố gắng hết sức".** Case đã ghi xong thì không được báo lỗi nữa: nếu khoá `assignments` bận hoặc Sheet lỗi, API vẫn trả case đã lưu (tránh người dùng bấm lại và sinh case trùng). Trạng thái việc sẽ được tính lại ở lần ghi sau của màn hình đó.
25. **Cột `status` của Assignments là giá trị suy ra** từ các thao tác case đã ghi vào AuditLog, nên việc cập nhật nó không ghi AuditLog riêng.
26. **Dòng AuditLog của case được ghi ngay sau khi nhả khoá bản ghi.** Khi nhiều người sửa cùng lúc, thứ tự các dòng AuditLog có thể lệch nhẹ so với thứ tự `version`.
27. **Danh sách test case, việc được giao và màn hình được cache trong Redis 60 giây** (`sheet_cache_ttl_seconds`), vì mỗi lần gọi Google mất khoảng 0,4 giây. Ghi xong là xoá cache ngay. Việc kiểm tra phiên bản khi lưu case và mọi lần đọc trong khoá (kiểm tra rồi ghi) luôn đọc thẳng Sheet, nên cache cũ không gây mất dữ liệu. Đổi lại: sửa tay trực tiếp trên Google Sheet có thể mất tới 60 giây mới hiện ra trong app. Điều này thay quyết định cũ "không cache test case" (spec 9.7).
28. **"Bị trả lại" không lưu thành một cột riêng.** Case Nháp có lần đổi trạng thái mới nhất là `RETURN` trong AuditLog thì coi là bị trả lại; lý do là nhận xét của dòng đó. "Việc của tôi" hiện danh sách này kèm nút "Viết lại".
29. **Duyệt hàng loạt: một khoá, một lần đọc, bỏ qua case lỗi.** `POST /test-cases/approve-batch` (tối đa 200 case một lượt) lấy khoá tab `test-cases` một lần và đọc Sheet một lần. Mỗi case vẫn kiểm tra version và trạng thái riêng, vẫn ghi AuditLog riêng. Case lỗi (version cũ, không phải Chờ duyệt, không tồn tại) được bỏ qua và trả về kèm lý do; các case còn lại vẫn được duyệt. Trạng thái việc tính lại một lần cho mỗi màn hình, sau khi nhả khoá. "Trả lại" vẫn làm từng case vì mỗi case cần một nhận xét riêng.
30. **Giữ nguyên spec cho luồng GitHub issue** (owner chọn 2026-11-13): AI đọc case đã duyệt trực tiếp từ Sheet; issue GitHub chỉ tạo cho case FAIL ở M5, không tạo khi duyệt.

## M4 — Worker chạy test bằng Playwright

31. **[Quyết định M4] Cấu hình app nằm ở `worker-projects.json` trên máy worker**, không ở Sheet và không có API sửa. Gồm `app_path`, `start_command`, `app_url`, tài khoản test và `login_steps`. Lý do: đường dẫn/lệnh chỉ có nghĩa trên máy này, không phải thêm cột vào Sheet đang dùng, và người dùng web không thể chèn lệnh chạy vào máy chủ dự án. Đổi lại: muốn đổi lệnh thì sửa file bằng tay.
32. **[Quyết định M4] Lý do một run `FAILED` lưu ở Redis** (`run:<id>:note`, hết hạn sau 30 ngày), vì tab `Runs` không có cột lý do và không thêm cột. Sau 30 ngày run vẫn hiện `FAILED` nhưng không còn lý do.
33. **[Quyết định M4] Mã kết quả = `<mã run>-<mã case>`** (ví dụ `RUN-0001-TC-000012`), không dùng bộ đếm, nên ghi lô không tốn lượt đọc/ghi `Meta`. Mỗi case chỉ chạy một lần trong một run nên không trùng.
34. **[Quyết định M4] Case thiếu bất kỳ bước tự động nào → `BLOCKED`** (nêu số bước thiếu), không chạy nửa chừng để tránh PASS giả. Lỗi của worker khi chạy một case → `INCONCLUSIVE`. Case chạy quá giờ → `INCONCLUSIVE`. Bước nào đó không đạt, kể cả khi bị giới hạn bởi thời gian còn lại của case → coi là hết giờ → `INCONCLUSIVE`.
35. **[Quyết định M4] "Chữ hiển thị" khớp CẢ chữ** (nút, link hoặc chữ trọn vẹn), không khớp một phần, để "Đăng nhập" không khớp nhầm tiêu đề "Trang đăng nhập". Còn "thấy chữ / không thấy chữ" vẫn khớp một phần. Tester cần ghi đúng nguyên chữ trên nút.
36. **[Quyết định M4] Chỉ nhận run còn `QUEUED`; chỉ chạy case còn `APPROVED` lúc chạy.** Huỷ run đang chờ thì đổi ngay sang `CANCELLED`; huỷ run đang chạy thì đặt cờ, worker dừng sau case hiện tại (kết quả đã chạy vẫn được ghi). Worker khởi động lại sẽ đổi run `RUNNING` bị bỏ dở thành `FAILED`.
37. **[Quyết định M4] Worker không cache Sheet** (`sheet_cache_ttl_seconds=0`) để thấy đúng case nào đang `APPROVED`. Worker tắt cả cây tiến trình của app bằng `psutil` (cả Windows lẫn Linux), vì `npm run dev` sinh nhiều tiến trình con.
38. **[Quyết định M4] Chưa có thông báo cho các role** (ví dụ báo QA Lead khi run xong hoặc có FAIL). Người dùng tự mở tab "Chạy test". Để sau M5.

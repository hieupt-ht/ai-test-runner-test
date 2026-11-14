# M4 — Worker chạy test bằng Playwright (thiết kế)

Ngày: 2026-11-14 · Trạng thái: **chờ chủ dự án duyệt** · Thay cho phần "review tĩnh bằng AI" của M4 trong spec gốc (mục 7.8, 7.7).

Quy ước nhãn như spec gốc: **[Chủ dự án]** = chủ dự án đã chốt; **[Đề xuất]** = mình (Claude) đề xuất, chủ dự án chưa xác nhận.

## 1. Mục đích

Có một worker chạy các test case đã duyệt trên **web thật chạy ở máy local**, bằng Playwright. Chủ dự án đóng vai QA, nên cần kết quả thật (bấm được hay không) chứ không phải AI đoán từ code.

**Vì sao đổi hướng:** hiện chưa có staging, nhưng có source của các app. Worker chạy app từ source ngay trên máy chủ dự án, nên không cần staging.

## 2. Mục tiêu / không phải mục tiêu

Mục tiêu:
- Chạy được các case `APPROVED` bằng Playwright và ghi PASS / FAIL / BLOCKED vào Sheet `Results`.
- FAIL ghi rõ **lỗi ở bước nào** và có **ảnh chụp**.
- Soạn được bước tự động trên form, case cũ vẫn mở và sửa bình thường.

Không làm trong M4:
- **Không dùng AI.** Sau này AI chỉ điền sẵn các bước tự động, cùng cấu trúc dữ liệu dưới đây. **[Chủ dự án]**
- Không Docker cho worker, không staging, không chạy song song nhiều run.
- Không tự tạo issue; luồng issue là M5.

Điều phải tránh (anti-goal): kết quả PASS giả. Không bước tự động thì không được PASS (xem 5).

## 3. Các hướng đã cân nhắc

| Hướng | Mô tả | Đánh đổi |
|---|---|---|
| 1. Viết script Playwright cho từng case | QA tự viết code | Linh hoạt nhất nhưng tester không viết được code; khó quản lý trong Sheet |
| **2. Bước có cấu trúc (đã chọn)** | Mỗi bước: hành động chọn từ danh sách + cách tìm phần tử + giá trị | Tester dùng được qua form; AI sau này điền được cùng cấu trúc; kém linh hoạt hơn script |
| 3. Bước viết bằng tiếng tự nhiên, AI diễn giải khi chạy | Không cần cấu trúc | Cần AI ngay, kết quả không lặp lại được; trái với việc tạm bỏ AI |

**[Chủ dự án]** chọn hướng 2.

## 4. Dữ liệu bước tự động

`TestStep` (backend `core/models/test_case.py`, frontend `lib/api/types.ts`) hiện chỉ có `action` và `expected` (chữ tự do). Thêm một trường **tuỳ chọn** `auto`:

```json
{
  "action": "Đăng nhập",
  "expected": "Vào được trang chủ",
  "auto": {
    "type": "fill",
    "target": { "by": "label", "value": "Email" },
    "value": "qa@example.com"
  }
}
```

- `type` (danh sách cố định): `goto` (mở trang), `fill` (nhập chữ), `click` (bấm), `select` (chọn), `see_text` (kiểm tra chữ **có** hiện), `not_see_text` (kiểm tra chữ **không** hiện), `url_is` (kiểm tra URL).
- `target.by`: `text` (chữ hiển thị) hoặc `label` (nhãn ô nhập) là mặc định; `css` chỉ để ở mục **Nâng cao**. `goto`, `see_text`, `not_see_text`, `url_is` không cần `target`.
- `value`: chữ cần nhập, tên lựa chọn, đường dẫn, chữ cần kiểm tra, hoặc URL.
- Lưu **trong JSON của cột `steps`**, **không thêm cột Sheet**. Case cũ không có `auto` vẫn đọc được. **[Chủ dự án]**
- Giới hạn độ dài `value`/`target.value` khoảng 500 ký tự như `action`. **[Đề xuất]**

## 5. Cách worker chạy một run

1. Run vẫn tạo ở `Runs` (`QUEUED`) và đẩy vào hàng đợi Redis như spec 7.7; mỗi dự án một run một lúc.
2. Worker **chạy thẳng trên máy chủ dự án (không Docker)** để dùng được `localhost`. **[Chủ dự án]**
3. Worker tự bật app của dự án: chạy `start_command` trong `app_path` (lấy từ `worker-projects.json`, mục 6), chờ `app_url` trả lời (timeout cấu hình được, mặc định 120 giây), chạy xong thì **tắt cả cây tiến trình** của app. **[Chủ dự án chọn "worker tự chạy app"]**
4. Web cần đăng nhập: worker dùng **một tài khoản test có sẵn** của dự án, đăng nhập một lần rồi dùng lại phiên cho các case của run. **[Đề xuất]** Đăng nhập bằng email/mật khẩu (mục 8.1).
5. Với mỗi case:
   - Không có bước nào có `auto` → ghi **BLOCKED**, lý do "chưa có bước tự động".
   - Có bước nhưng bước nào đó thiếu `auto` → BLOCKED, ghi rõ bước số mấy thiếu. **[Đề xuất]** (để tránh PASS giả khi chỉ chạy được một phần)
   - Chạy từng bước theo thứ tự trong một ngữ cảnh trình duyệt mới. Mọi bước xong → **PASS**. Có bước lỗi (không thấy phần tử, sai chữ, sai URL, quá giờ) → **FAIL**, ghi `failed_step`, thông báo lỗi ngắn tiếng Việt, và **ảnh chụp** lúc lỗi.
   - Lỗi của chính worker (app không lên, trình duyệt sập) → **INCONCLUSIVE**, không tính FAIL cho case. **[Đề xuất]**
   - PASS/FAIL **do Playwright quyết định**. **[Chủ dự án]**
6. Timeout mỗi bước 10 giây, mỗi case 2 phút (cấu hình qua env). **[Đề xuất]**
7. **Ghi Sheet theo lô** (mỗi 10 case hoặc 30 giây) như spec mục 9.5, chỉ vào `Runs` và `Results`. **[Chủ dự án]**
8. Có thể huỷ run: kiểm tra cờ huỷ giữa các case; xong thì dọn app, trình duyệt, file tạm.

### Ảnh chụp
Lưu ở thư mục `artifacts/<run_id>/` trên máy worker (bỏ qua git), không đưa vào Sheet. Cột `Results.evidence` chỉ giữ đường dẫn tương đối. API trả ảnh cho người có quyền xem dự án; việc hiển thị ảnh trên giao diện cho làm ở M4 nếu kịp, không thì M5. **[Đề xuất]**

## 6. Cấu hình dự án

**Thay đổi so với bản đầu [Đề xuất]:** `app_path`, `start_command`, `app_url` và tài khoản test (email, mật khẩu) đều để trong **một file cấu hình riêng trên máy worker**, `worker-projects.json` ở thư mục gốc repo (đã gitignore), theo `project_id`:

```json
{ "PRJ-0001": {
    "app_path": "D:/code/shop", "start_command": "npm run dev", "app_url": "http://localhost:3000",
    "test_email": "qa@x.com", "test_password": "...",
    "login_steps": [
      { "type": "goto", "value": "/login" },
      { "type": "fill", "target": { "by": "label", "value": "Email" }, "value": "{email}" },
      { "type": "fill", "target": { "by": "label", "value": "Mật khẩu" }, "value": "{password}" },
      { "type": "click", "target": { "by": "text", "value": "Đăng nhập" } }
    ] } }
```

`login_steps` dùng đúng cấu trúc bước tự động ở mục 4; `{email}` và `{password}` được thay bằng tài khoản test. Worker chạy các bước này **một lần đầu run**, lưu phiên đăng nhập của trình duyệt, rồi mỗi case dùng lại phiên đó. Đăng nhập lỗi thì cả run `FAILED` (không ghi FAIL cho từng case).

Lý do: đường dẫn và lệnh chạy chỉ có ý nghĩa trên máy này; không phải thêm cột vào tab `Projects` (sheet đang dùng sẽ không bị lỗi thiếu cột); và **không có API hay giao diện nào sửa được lệnh chạy**, nên không ai chèn được lệnh lạ vào máy bạn qua web. Đổi lại: muốn đổi lệnh thì sửa file bằng tay. Dự án chưa có trong file thì run bị `FAILED` kèm lý do rõ ràng.

Worker chỉ chạy lệnh có trong file, không bao giờ chạy lệnh lấy từ test case.

## 6.1 Phạm vi M4 (đủ để chạy được từ đầu đến cuối)

- Backend: kho `Runs` và `Results` (tab đã có sẵn trong schema), API tạo run / xem run / xem kết quả / huỷ run / lấy ảnh chụp, hàng đợi Redis, worker.
- Frontend: phần "Tự động" trên form (mục 7) và một tab **"Chạy test"** trong dự án: nút chạy (chỉ `TRIGGER_RUN`), tiến độ (polling), danh sách kết quả của run kèm lý do, bước lỗi và ảnh chụp. Màn hình kết quả đầy đủ, "AI sai" và tạo issue là M5. **[Đề xuất]**
- Chưa có thông báo cho các role (ví dụ báo cho QA Lead khi run xong hoặc có FAIL). Người dùng tự mở tab "Chạy test" để xem. Thông báo để sau M5. **[Đề xuất]**

## 7. Form tạo/sửa case

`steps-editor.tsx` thêm phần **"Tự động"** cho mỗi bước, mặc định **thu gọn**: chọn hành động, chọn cách tìm (chữ/label), nhập giá trị; mục **Nâng cao** cho CSS selector. **[Chủ dự án]**

**Cần làm trước:** chủ dự án báo form hiện tại đang "vỡ" ở vài chỗ (chưa nói chi tiết). Sửa chỗ vỡ trước, rồi mới thêm phần mới. Chi tiết cần ảnh chụp từ chủ dự án.

## 8. Còn mở

1. ~~Đăng nhập app test~~ **Đã chốt [Chủ dự án]:** app đầu tiên đăng nhập bằng **email/mật khẩu**, không dùng Google. Worker dùng một tài khoản tạo sẵn bằng tay. Chủ dự án chưa nhắc tới xác thực email/captcha nên mình coi như **không có**; nếu sau này app có thì tài khoản tạo sẵn vẫn dùng được. **[Đề xuất]**
2. **App đầu tiên để thử:** đường dẫn repo, lệnh chạy, URL (chủ dự án sẽ gửi).
3. **Ai được tạo issue:** chưa quyết. Mặc định theo spec 7.9 (DECISIONS 30): QA Lead/Admin xem FAIL rồi bấm "Tạo issue"; tester chưa được. Làm ở M5, đổi quyền sau chỉ là sửa một chỗ trong `permissions.py`.

## 9. Việc để builder quyết

Tên module trong `backend/app/worker/`, cách đóng gói Playwright (Python `playwright`), cách tắt cây tiến trình trên Windows, định dạng chính xác của file cấu hình tài khoản test, và bố cục chi tiết của phần "Tự động" trên form (miễn đúng mục 7).

## 10. Kiểm thử

- Unit test: validate `auto`, đọc case cũ không có `auto`, quy tắc BLOCKED/PASS/FAIL, ghi lô.
- Thử với một trang web nhỏ do test tự dựng (không phụ thuộc app thật).
- Chạy thử một lần với app thật của chủ dự án khi có thông tin ở mục 8.

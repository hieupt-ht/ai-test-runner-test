# Nhập kết quả từ Excel, chạy hàng loạt, "Lưu và chạy" — thiết kế

Ngày 2026-11-27. Chủ dự án đã chốt hướng trong buổi trao đổi cùng ngày.

## 1. Vì sao làm

Tester nhờ AI viết test case ra Excel (bước làm, dữ liệu test…), rồi nhập vào app. Có bạn đã
test xong trên Excel nên file có thêm cột kết quả (Pass/Fail), có bạn chưa test nên file chỉ có
nội dung case. Hiện app:

- Không đọc được cột kết quả trong file (file mẫu chỉ có 16 cột nội dung).
- Chỉ chạy được từng case một (mở case → bảng chạy tay → gửi). Chạy 30 case là bấm 30 lần.
- Bắt buộc ảnh/video khi Fail, nên kết quả Fail từ Excel (không có ảnh) không ghi được.
- Nút "Nhập từ Excel" bị ẩn trong vài trường hợp sau khi có module (xem 3.1).

**Mục tiêu:** nhập file có hoặc không có kết quả đều được; case có kết quả thì chạy nhanh (từng
cái hoặc hàng loạt) và bắn issue lên GitHub cho case Fail; tạo case trên web thì chạy được luôn.

**Không làm:**

- Nhập file **không bao giờ** tự chạy case hay tạo issue. Chạy luôn là một bước người dùng bấm.
- Không nhập ảnh/video từ Excel.
- Không đổi luật cho kết quả do agent (Codex) gửi.
- Không sửa nội dung case đã có khi nhập lại file.

**Thất bại dù chạy được:** issue bắn lên GitHub ngay lúc nhập file; nhập lại file làm hỏng
nội dung case đã chỉnh trong app; tester đang chạy dở 20 case thì lỡ đóng trang và mất hết.

## 2. Các cách đã cân nhắc (chỗ giữ kết quả chờ chạy)

| Cách | Ưu | Nhược |
|---|---|---|
| **A. Thêm cột "kết quả chờ" vào tab `TestCases`** (đã chọn) | Đọc một tab là biết case nào sẵn sàng chạy; không tốn thêm lượt gọi Google; app tự thêm cột như lần thêm `module_id` | Tab TestCases có vài cột không thuộc nội dung case |
| B. Tab mới `PendingResults` | Dữ liệu tách bạch | Mọi trang phải đọc thêm một tab, thêm khoá, xoá case phải dọn hai nơi |
| C. Ghi vào tab `Results` với trạng thái "Chờ" | Không cần chỗ mới | Thống kê, bảng xếp hạng, đồng bộ issue đều đọc `Results`; phải sửa khắp nơi để bỏ qua "Chờ", rất dễ sót |

Chủ dự án chọn **A**.

## 3. Phần 1 (nhỏ, làm trước)

### 3.1 Nút "Nhập từ Excel" bị ẩn

Hiện `canImport` (trang Test case) cần **ít nhất một màn hình chọn được**. Với module, điều này
sai: tester vừa nhận một module trống, hoặc QA ở dự án chưa có màn hình nào, không thấy nút dù
nhập theo module sẽ tự tạo màn hình.

Luật mới: hiện nút khi có quyền tạo case và dự án không lưu trữ. Không cần có sẵn màn hình hay
module, vì trong hộp thoại ai cũng tạo được module mới (3.2) rồi nhập vào đó. (Sửa sau khi duyệt:
bản đầu còn đòi "có màn hình hoặc module", khiến tester chưa có gì không bao giờ thấy lối tắt tạo
module.) Danh sách module trong hộp thoại giữ nguyên luật hiện tại.

### 3.2 Tester tự tạo module

- `POST /modules` mở cho tester (cùng quyền như nhận module: `EDIT_TEST_CASE`). QA/Admin giữ như cũ.
- Tên không trùng (luật hiện có: so `name_key`, báo "Đã có module tên này").
- Tester tạo xong thì **tự nhận module đó**, hạn mặc định hôm nay + 7 ngày. Tạo module và nhận
  là một request; nhận lỗi thì xoá module vừa tạo (không để module mồ côi).
- Đổi tên, sửa mô tả, xoá module: **chỉ QA/Admin** như hiện tại.
- Giao diện: trang Màn hình hiện nút "Tạo module" cho tester; hộp thoại nhập Excel có lối tắt
  "+ Tạo module mới" ngay dưới ô chọn module (tạo xong chọn luôn module đó).

### 3.3 Bằng chứng không bắt buộc

- Bỏ luật 422 "Kết quả Fail cần ít nhất một ảnh hoặc video bằng chứng" ở `POST .../manual-results`.
- `ManualRunPanel`: chọn Fail mà chưa có ảnh/video thì nút Gửi **vẫn bấm được**, chỉ hiện dòng
  vàng "Nên thêm ảnh hoặc video để dev dễ tìm lỗi".
- Cập nhật `DECISIONS.md` (luật cũ ghi "FAIL cần bằng chứng").

## 4. Phần 2 (lớn)

### 4.1 File Excel: thêm 3 cột tuỳ chọn ở cuối

Sau 16 cột hiện có, file **có thể** có thêm, đúng thứ tự:

| Cột | Ý nghĩa | Giá trị |
|---|---|---|
| Kết quả sau test | kết quả thực tế | chữ, tối đa 2000 ký tự |
| Trạng thái | kết quả chạy | Pass / Fail / Blocked (không phân biệt hoa thường; nhận thêm "Đạt", "Không đạt", "Bị chặn") |
| Bước lỗi | bước bị lỗi (khi Fail) | số từ 1 tới số bước của case |

- File có **16, 17, 18 hoặc 19 cột** đều hợp lệ, miễn các cột thêm đúng tên và đúng thứ tự trên.
  File cũ 16 cột chạy như hôm nay.
- Ba cột này là mức **case** (ghi ở dòng đầu của nhóm, các dòng sau để trống hoặc giống hệt), như
  các cột case khác.
- File mẫu tải về có đủ 19 cột, ô Trạng thái có danh sách chọn Pass/Fail/Blocked.

**Kiểm tra từng case khi đọc file** (lỗi thì cả file không nhập, như hiện nay):

- Trạng thái trống: case **không có kết quả chờ** (chỉ tạo case). Kết quả sau test/Bước lỗi có ghi
  cũng bỏ qua, kèm **cảnh báo** "Không có Trạng thái nên bỏ qua kết quả".
- Trạng thái lạ: lỗi "Trạng thái phải là Pass, Fail hoặc Blocked".
- Fail hoặc Blocked mà **Kết quả sau test trống**: lỗi "Fail/Blocked cần ghi Kết quả sau test".
- Bước lỗi không phải số, hoặc ngoài khoảng 1..số bước: lỗi. Bước lỗi ghi khi Pass/Blocked: bỏ qua
  kèm cảnh báo.
- Fail không có ảnh: **không** cảnh báo ở bước nhập (Excel vốn không có ảnh); cảnh báo hiện ở lúc chạy.

### 4.2 Nhập lại file có case đã có

Hiện app **báo lỗi** case trùng (cùng màn hình, cùng tiêu đề sau khi chuẩn hoá). Đổi thành:

- Case **đã có** (cùng màn hình + cùng tiêu đề chuẩn hoá): **không tạo mới, không sửa nội dung**.
  Nếu dòng có Trạng thái thì ghi đè **kết quả chờ** của case đó; không có Trạng thái thì bỏ qua dòng.
- Case đã có mà đang **Chờ duyệt / Đã duyệt / Lưu trữ / Ngừng dùng**, hoặc chạy **Tự động**: dòng có
  Trạng thái thì báo lỗi dòng "Case đang <trạng thái>, chưa ghi kết quả được"; dòng không có
  Trạng thái thì bỏ qua.
- Tester chỉ ghi kết quả chờ cho case mình **chạy được** (`can_run`); không thì lỗi dòng
  "Bạn không được chạy case này".
- Hai dòng cùng tiêu đề trong **cùng một file** vẫn là lỗi như hiện nay.
- Màn xem trước ghi rõ: "12 case: 4 mới, 6 đã có (chỉ cập nhật kết quả chờ), 2 đã có (bỏ qua)".
  Bảng xem trước có thêm cột Trạng thái.

### 4.3 Kết quả chờ (cột mới ở tab `TestCases`)

Nối vào **cuối** `TEST_CASE_COLUMNS` (app tự thêm khi khởi động):

- `pending_status`: `PASS` / `FAIL` / `BLOCKED` / trống
- `pending_actual`: kết quả sau test
- `pending_failed_step`: số hoặc trống

Model `TestCase` có thêm `pending: PendingResult | None` (`None` khi `pending_status` trống).

- Ghi/xoá kết quả chờ **không** tăng `version` của case và **không** đổi `updated_at`/`updated_by`
  (không phải sửa nội dung; tránh làm người đang mở case bị báo "Case vừa được sửa"). Có ghi
  AuditLog (`action = "PENDING_RESULT"`).
- Sửa nội dung case trong app: **giữ** kết quả chờ. Nếu số bước giảm tới mức `pending_failed_step`
  vượt số bước thì xoá `pending_failed_step` (giữ trạng thái và kết quả sau test).
- Chạy case (bằng bất kỳ đường nào: chạy tay từng case, chạy hàng loạt, "Lưu và chạy") thành công
  thì **xoá kết quả chờ** của case đó.
- API danh sách/chi tiết case trả thêm `pending`.

### 4.4 Chạy hàng loạt

**Giao diện** (trang Test case):

- Danh sách case có thêm bộ lọc nhanh "Sẵn sàng chạy (N)" (có kết quả chờ, chạy được) và
  "Thiếu kết quả (M)" (Manual, Nháp/Đã kiểm thử, không có kết quả chờ, chạy được).
- Cột trạng thái chạy: case có kết quả chờ hiện nhãn "Chờ chạy: Fail" (màu theo kết quả).
- Tick chọn nhiều case (có sẵn ô tick cho duyệt hàng loạt) → nút **"Chạy N case"** → mở bảng chạy:

```
Môi trường: [Pixel 7 / Android 14]   Bản build: [1.4.2]          Đã chạy 5/12
[Đánh tất cả chưa chọn là Pass]

✓ TC-0012  Đăng nhập thành công   Pass
✓ TC-0013  Sai mật khẩu           Fail · issue #41             [+ Ảnh]
  TC-0014  Quên mật khẩu          (Pass) (●Fail) (Blocked)
           Kết quả sau test: [Hiện lỗi 500.............]  Bước lỗi: [2 ▾]  [+ Ảnh]
           ⚠ Chưa có ảnh/video — nên thêm để dev dễ tìm lỗi          [Lưu]
  TC-0015  Đăng xuất              (Pass) (Fail) (Blocked)
```

- Dòng có kết quả chờ thì **điền sẵn** từ đó (tester chỉ cần xem lại rồi lưu).
- **Lưu ngay từng dòng**, không đợi cuối buổi: Pass bấm là lưu; Fail/Blocked bấm Lưu sau khi có
  Kết quả sau test. Dòng đã lưu hiện ✓ (Fail có link issue khi đã có) và không lưu lại được trong
  bảng này (muốn chạy lại thì mở case).
- Nút **"Lưu tất cả"** gửi mọi dòng đã chọn kết quả mà chưa lưu, trong **một** request.
  "Đánh tất cả chưa chọn là Pass" chỉ điền giao diện, chưa lưu.
- Môi trường bắt buộc (như chạy tay hiện nay), nhập một lần cho cả bảng; nhớ lần nhập gần nhất
  trên trình duyệt. Bản build không bắt buộc.
- Đóng bảng khi còn dòng đã chọn mà chưa lưu: hỏi lại "Còn N kết quả chưa lưu".

**API mới:** `POST /projects/{pid}/test-cases/batch-results`

```json
{
  "environment": "Pixel 7 / Android 14",
  "build_version": "1.4.2",
  "items": [
    {"case_id": "TC-0013", "version": 3, "status": "FAIL", "actual_result": "Hiện lỗi 500",
     "failed_step": 2, "evidence": {"screenshots": []}}
  ]
}
```

- Tối đa 50 case một request. Một request = **một Run** (`total` = số case ghi được, `passed`/
  `failed` đếm theo kết quả), một lần ghi tab `Results`, một lần ghi AuditLog.
- Mỗi case xét **riêng**: case không chạy được (không quyền, sai trạng thái, `version` lệch, case tự
  động, dữ liệu sai) thì bỏ qua và trả lỗi của riêng case đó; các case khác vẫn ghi. Không case nào
  ghi được thì không tạo Run và trả 422 kèm danh sách lỗi.
- Trả về `{run_id, saved: [{case_id, case}], errors: [{case_id, message}]}`.
- Kết quả từng bước do server dựng (người chạy hàng loạt không chấm từng bước):
  - Pass: mọi bước PASS.
  - Fail có bước lỗi k: bước 1..k−1 PASS, bước k FAIL, sau đó SKIPPED.
  - Fail không có bước lỗi, và Blocked: mọi bước SKIPPED.
- `reason` của Result = Kết quả sau test (Fail/Blocked). `actual_result` = Kết quả sau test.
- Sau khi ghi: như chạy tay hiện nay cho từng case (case Pass/Fail → TESTED, xoá kết quả chờ,
  thông báo người tạo case Fail, tạo/cập nhật issue cho case Pass/Fail, dọn bằng chứng cũ), gom
  lại để không gọi Google theo từng case khi có thể. Đồng bộ issue chạy nền như hiện nay.
- Luật Fail chạy tay hiện tại yêu cầu `failed_step`; ở đây **bước lỗi không bắt buộc** (chủ dự án
  chốt). Cho đồng bộ, `POST .../manual-results` cũng bỏ bắt buộc `failed_step` khi Fail.

### 4.5 "Lưu và chạy" khi tạo case trên web

- Form tạo case (case Manual) có hai nút: **"Lưu"** (như cũ) và **"Lưu và chạy"**.
- "Lưu và chạy" mở phần kết quả ngay dưới form: Trạng thái, Kết quả sau test, Bước lỗi, Môi trường,
  Bản build, ảnh/video (tuỳ chọn) — cùng luật như một dòng của bảng chạy hàng loạt.
- Cách gửi: tạo case trước (API tạo như cũ), thành công thì gọi `batch-results` với một case.
  Bước chạy lỗi thì case **vẫn đã tạo**: báo "Đã lưu case nhưng chưa chạy được: …" và chuyển tới
  trang case để chạy lại.
- Case Tự động không có nút "Lưu và chạy".

## 5. Lỗi và giới hạn

- Khoá: giữ thứ tự hiện có (screens → assignments → module-assignments → test-cases → runs/results).
  `batch-results` giữ khoá test-cases trong lúc kiểm tra `version` và xoá kết quả chờ.
- Khoá bận: 409 "Đang có người ghi kết quả, hãy thử lại" (bảng chạy giữ nguyên các dòng chưa lưu).
- Google lỗi khi ghi Results: 503, không dòng nào được đánh dấu ✓.
- Case vừa bị sửa (lệch `version`): lỗi riêng dòng đó "Case vừa được sửa, hãy tải lại".

## 6. Kiểm tra

- Backend: đọc file 16/17/18/19 cột; sai tên cột thêm; từng luật ở 4.1; nhập lại case đã có (cập
  nhật kết quả chờ, không đổi nội dung/version); case sai trạng thái; tester không chạy được;
  `batch-results` (Run một lần ghi, lỗi riêng từng case, dựng kết quả từng bước, xoá kết quả chờ,
  TESTED, issue cho Fail); Fail không bằng chứng được nhận; tester tạo module tự nhận.
- Frontend: nút nhập hiện với module trống; tạo module từ hộp thoại nhập; bảng chạy (điền sẵn, lưu
  từng dòng, lưu tất cả, hỏi khi đóng còn dòng chưa lưu); "Lưu và chạy" (tạo ok + chạy lỗi).

## 7. Quyết định của Claude (chủ dự án xem lại)

- Nhận thêm chữ tiếng Việt cho Trạng thái ("Đạt", "Không đạt", "Bị chặn").
- Blocked cũng bắt buộc Kết quả sau test (lý do bị chặn), như Fail.
- Fail không có bước lỗi và Blocked: mọi bước SKIPPED.
- Ghi kết quả chờ không tăng `version` của case.
- Dòng đã lưu trong bảng chạy không lưu lại được; muốn chạy lại thì mở case.
- Một request `batch-results` tối đa 50 case; mỗi request là một Run.
- Tester tạo module được hạn mặc định hôm nay + 7 ngày.
- Bỏ luôn bắt buộc `failed_step` ở chạy tay để luật hai đường giống nhau.

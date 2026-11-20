# Nhập test case từ Excel và khoá case do QA viết — thiết kế

Ngày: 2026-11-19 · Nhánh: `feature/ai-agent-runner`

## Vì sao làm

Ở công ty, QA hoặc tester đọc tài liệu yêu cầu (SRS, user story, Figma), tách ra test case trong
Excel theo mẫu, rồi tester chạy theo. Hiện app chỉ tạo được **từng case một qua form**, nên phải
gõ lại cả file vào. Chủ dự án muốn:

- QA (và cả tester, "cho lẹ") **nhập cả file test case** vào app một lần, file phải **đúng mẫu**.
- Tester **chỉ việc chạy**: tick từng bước, chọn Pass/Fail, ghi lý do lỗi, đính bằng chứng.
  Khung "Chạy test tay" (`ManualRunPanel`, spec `2026-11-18-manual-test-run-design.md`) đã làm
  được việc này.
- Case do QA viết thì tester **không được sửa** (chủ dự án chọn "khoá lại").

## Mục tiêu

1. Tải được **file mẫu .xlsx** từ app.
2. Nhập file .xlsx: **một file cho nhiều màn hình**, mỗi dòng là một bước, các dòng cùng
   "Mã nhóm" gom thành một case. App **xem trước** và báo lỗi theo từng dòng. Có lỗi thì không
   ghi gì. Hết lỗi thì bấm Xác nhận, app tạo mọi case cùng lúc.
3. Ai tạo được case thì nhập được: QA Lead/Admin nhập cho mọi màn hình, tester chỉ nhập cho
   màn hình được giao.
4. **Khoá theo người tạo:** tester chỉ sửa case **mình tạo**. Case người khác tạo (QA Lead,
   Admin hay tester khác) trên màn hình được giao thì tester **chỉ chạy**.
5. Gửi kết quả **FAIL** bắt buộc có ít nhất 1 ảnh hoặc video bằng chứng.

## Không làm

- Nhập **kết quả đã chạy** (cột Actual/Status) từ Excel.
- Nhập ảnh/video hướng dẫn từ file. Nhập xong, người có quyền sửa vào app gắn thêm.
- Nhập case Automation: case nhập luôn là `MANUAL`, file không có cột "Cách chạy".
- Nhập để **sửa** case đã có (cập nhật theo mã). Lần nhập nào cũng chỉ tạo case mới.
- File CSV, đọc thẳng link Google Sheet, tab "Nhập case" trong Sheet dự án.
- Tự tạo màn hình còn thiếu.

## Chống mục tiêu (làm thế này là hỏng)

- Nhập được một nửa file: một số case đã ghi, phần còn lại lỗi, người dùng nhập lại thì trùng.
- Một lần nhập làm app vượt hạn mức đọc/ghi Google Sheets (khoảng 60 lần/phút), khiến cả app
  báo lỗi cho người khác.
- App đoán nghĩa của file sai mẫu rồi tạo ra case sai, không ai biết.
- Tester sửa được case do QA viết, kể cả bằng cách gọi API trực tiếp.
- Tester nhập được case vào màn hình không giao cho mình.

## Các cách đã xét

- **A. Tải file .xlsx lên (đã chọn).** QA viết trong Excel, hoặc trong Google Sheets rồi tải về
  .xlsx. Không phải chia quyền Sheet, không tốn lượt đọc Google, dễ test tự động. Đổi lại: thêm
  bước tải xuống/tải lên và thêm thư viện `openpyxl`.
- B. Tab "Nhập case" trong Sheet dự án: QA phải có quyền sửa Sheet dữ liệu chính (dễ sửa nhầm
  `TestCases`/`Results`), và phải dọn dòng đã nhập để khỏi nhập trùng. Bỏ.
- C. Dán link Google Sheet bất kỳ: mỗi file phải chia sẻ cho Service Account, hay lỗi quyền,
  thêm một luồng đọc Sheet lạ. Có thể làm sau, dùng lại phần xem trước. Bỏ ở đợt này.

Về khoá: xét "khoá case được đánh dấu là nhập từ file" và "khoá theo người tạo". Chọn **theo
người tạo** (đề xuất của Claude, chủ dự án đồng ý): không cần thêm cột đánh dấu, luật dễ nhớ,
case QA tạo bằng form cũng được khoá như case QA nhập.

## Thiết kế

### 1. Mẫu file

Một sheet tên `Test case`, dòng 1 là tiêu đề, dữ liệu từ dòng 2. Thứ tự cột:

| # | Tiêu đề cột (đúng chữ) | Trường | Bắt buộc | Mức case/bước |
|---|---|---|---|---|
| 1 | Mã nhóm | (gom dòng) | có | — |
| 2 | Màn hình | `screen_id` (dò theo tên) | có | case |
| 3 | Mã yêu cầu | `requirement_ref` | | case |
| 4 | Tiêu đề | `title` | có | case |
| 5 | Điều kiện trước | `precondition` | | case |
| 6 | Dữ liệu test | `test_data` | | case |
| 7 | Điểm bắt đầu | `start_point` | | case |
| 8 | Bước làm | `steps[].action` | có (mỗi dòng) | bước |
| 9 | Mong đợi của bước | `steps[].expected` | | bước |
| 10 | Kết quả mong đợi | `expected_result` | có | case |
| 11 | Điều kiện sau | `postcondition` | | case |
| 12 | Mức độ | `severity`: LOW/MEDIUM/HIGH | có | case |
| 13 | Ưu tiên | `priority`: P1/P2/P3 | có | case |
| 14 | Nền tảng | `platform`: WEB/ANDROID/IOS, trống = WEB | | case |
| 15 | Loại test | `test_type`: FUNCTIONAL/UI, trống = FUNCTIONAL | | case |
| 16 | Regression | `regression`: Có/Không, trống = Không | | case |

- Danh sách cột và các trường tương ứng chỉ khai báo **một chỗ** trong backend. File mẫu, bộ
  đọc file và test đều dùng chung danh sách này.
- **Kiểm tra tiêu đề:** dòng 1 phải có đủ 16 cột đúng chữ (bỏ khoảng trắng hai đầu, không phân
  biệt hoa thường), đúng thứ tự. Sai thì báo một lỗi "File không đúng mẫu, hãy tải file mẫu
  mới", kèm tên cột sai đầu tiên, và không đọc tiếp. Cột thừa ở bên phải được bỏ qua.
- **Gom dòng:** các dòng cùng "Mã nhóm" thành một case, bước theo thứ tự dòng. Dòng **đầu tiên**
  của nhóm mang các ô mức case. Ở các dòng sau, ô mức case phải trống hoặc giống hệt dòng đầu,
  khác thì báo lỗi (chống gõ nhầm Mã nhóm làm hai case dính vào nhau). Một nhóm phải nằm **liền
  nhau**: nhóm xuất hiện lại sau nhóm khác thì báo lỗi.
- Dòng trống hoàn toàn thì bỏ qua. Dòng có dữ liệu mà thiếu "Mã nhóm" thì báo lỗi.
- **Màn hình:** dò theo tên màn hình trong dự án (bỏ khoảng trắng hai đầu, không phân biệt hoa
  thường), không tìm thấy thì báo lỗi. Ô có thể ghi mã màn hình (`SCR-0001`) thay cho tên
  (*quyết định của Claude*: dùng khi hai màn hình trùng tên; trùng tên mà ghi tên thì báo lỗi
  "Có nhiều màn hình tên này, hãy ghi mã màn hình").
- **Giá trị chọn:** Mức độ, Ưu tiên, Nền tảng, Loại test, Regression nhận đúng mã trong bảng
  (không phân biệt hoa thường). Regression nhận thêm `Yes/No`, `TRUE/FALSE`, `x`/trống.
  File mẫu có **danh sách chọn sẵn** (data validation) cho các cột này.
- Ô có công thức thì lấy giá trị đã tính (`data_only=True`). Ô số hoặc ngày đọc thành chuỗi.
- Độ dài và số bước kiểm tra bằng chính `TestCaseContent`/`TestStep`: tối đa 50 bước, tiêu đề
  200 ký tự… Lỗi Pydantic được dịch sang câu tiếng Việt kèm số dòng.
- Giới hạn (*quyết định của Claude*): file ≤ 2 MB, ≤ 2000 dòng dữ liệu, ≤ 300 case một lần.
  Quá giới hạn thì báo lỗi, không đọc tiếp. Chỉ nhận `.xlsx`.

File mẫu tải về có dòng tiêu đề (in đậm, cố định khi cuộn), danh sách chọn, 1 case ví dụ 3 bước,
và một sheet `Hướng dẫn` ghi luật ở trên bằng tiếng Việt. Sheet `Hướng dẫn` bị bỏ qua khi đọc
(bộ đọc chỉ đọc sheet `Test case`, không có thì đọc sheet đầu tiên).

### 2. API

Mọi endpoint nằm dưới `/api/projects/{project_id}/test-cases/import`. Người gọi phải là thành
viên và có quyền tạo case (`EDIT_TEST_CASE`). Dự án lưu trữ thì 409.

- `GET .../import/template`: trả file mẫu `.xlsx` (tên `mau-test-case.xlsx`).
- `POST .../import/preview` (multipart, trường `file`): đọc và kiểm tra, **không ghi gì**. Trả:
  ```
  {
    "cases": [ { "group": "A1", "row": 2, "screen_id": "SCR-0001", "screen_name": "Đăng nhập",
                 "title": "...", "step_count": 3, "content": <TestCaseContent> } ],
    "errors":   [ { "row": 7, "column": "Kết quả mong đợi", "message": "Không được để trống" } ],
    "warnings": [ { "row": 2, "message": "Màn hình Đăng nhập đã có case cùng tiêu đề" } ]
  }
  ```
  `row` là số dòng trong Excel (dòng tiêu đề là 1). Lỗi tiêu đề cột hoặc vượt giới hạn trả về
  ở `errors` với `row = 1` (hoặc `null`), `cases` rỗng.
- `POST .../import` (multipart, cùng file): **đọc và kiểm tra lại từ đầu** rồi mới ghi.
  Còn lỗi thì 422 kèm cùng danh sách `errors`. Thành công thì 201 `{ "created": [<mã TC>…] }`.
  *(Quyết định của Claude: không lưu trạng thái giữa hai bước. Frontend gửi lại đúng file đã xem
  trước, nên server không phải giữ file hay phiên nhập nào.)*

**Quyền theo dòng:** tester chỉ nhập vào màn hình mình được giao. Nhóm có màn hình không được
giao thì báo lỗi ở dòng đó: "Bạn chưa được giao màn hình này". QA Lead/Admin nhập được mọi màn
hình.

**Cảnh báo trùng:** case trong file có cùng tiêu đề (bỏ khoảng trắng, không phân biệt hoa
thường) với case đã có trên cùng màn hình (trừ case lưu trữ/ngừng dùng) thì ghi vào `warnings`.
Cảnh báo **không chặn** việc nhập, chỉ để người dùng phát hiện mình vừa nhập lại file cũ.

### 3. Ghi hàng loạt (trọng tâm: không vượt hạn mức Sheet)

Tạo từng case bằng `TestCaseService.create` sẽ tốn khoảng 4–5 lượt gọi Google mỗi case
(cấp mã ở tab `Meta`, ghi dòng, ghi AuditLog, tính lại trạng thái việc). Với 100 case thì vượt
hạn mức. Vì vậy:

- `IdGenerator` có thêm hàm **cấp một lô mã** `next_ids(entity, prefix, count, digits)`: một lần
  đọc và một lần ghi tab `Meta`, trong cùng khoá Redis như `next_id`.
- `TestCaseRepository.create_many(items, actor)`: giữ khoá tab, cấp lô mã, rồi ghi mọi dòng bằng
  **một** lời gọi `append_many`, xoá cache một lần.
- `TestCaseService.import_cases(user, items)`: trong khoá tab (thứ tự khoá như `create`:
  assignments trước, test-cases sau), kiểm tra lại các màn hình còn tồn tại, rồi `create_many`.
  Sau khi ghi:
  - AuditLog: thêm `AuditLogRepository.record_many` ghi mọi dòng bằng một lời gọi, action
    `IMPORT`, diff như `CREATE` (đã bỏ media).
  - Tính lại trạng thái việc **một lần cho mỗi màn hình** bị đụng tới.
  - Lỗi AuditLog/trạng thái việc sau khi case đã ghi thì chỉ ghi log, không báo lỗi request
    (giống `_refresh_status`), để người dùng không bấm lại và sinh case trùng.
  - Không đồng bộ issue: case Manual ở `DRAFT` chưa có issue (issue chỉ tạo khi sang `TESTED`).
- **Hết hoặc không có gì:** lỗi Sheet ở bước cấp mã hoặc `append_many` (trước khi có dòng nào
  được ghi) thì trả 503 "Google Sheets đang bận, chưa nhập case nào, hãy thử lại". Mã đã cấp mà
  không dùng thì bỏ (mã nhảy cóc là chấp nhận được).
- Khoá bận (`LockTimeout`) thì 409 "Có người đang tạo case, hãy thử lại".
- Case nhập vào: `execution_mode = MANUAL`, `status = DRAFT`, `created_by` = người nhập,
  `version = 1`, không có media.

### 3b. Trạng thái việc: đếm mọi case của màn hình (quyết định của chủ dự án, cách 1)

Hiện `derive_assignment_status` chỉ đếm case do chính tester tạo, nên QA nhập case giao cho
tester thì việc của tester mãi là "Chưa làm". Đổi thành:

- Đếm **mọi case chưa ngừng dùng của màn hình**, ai tạo cũng tính (bỏ điều kiện `created_by`).
- Màn hình chưa có case nào → `TODO` (như cũ).
- Còn case `DRAFT` → `WRITING`; còn `IN_REVIEW` → `IN_REVIEW`; mọi case Manual đã `TESTED`
  hoặc mọi case đã chạy → `TESTED`; còn lại → `APPROVED` (như cũ).
- Nhiều tester cùng được giao một màn hình thì **ai chạy cũng tính**: case đã `TESTED` là xong,
  không cần từng tester chạy riêng. Hệ quả: các tester cùng màn hình có chung một trạng thái.
- Đổi chữ hiển thị `WRITING` từ "Đang viết" thành **"Đang làm"** (`frontend/messages/vi.json`).
  Giá trị `WRITING` trong Sheet và API giữ nguyên, không thêm trạng thái mới.
- Cần sửa test cũ theo luật mới (`test_assignment_status.py`, `test_assignments_api.py`) và
  thêm test: case do người khác tạo vẫn được tính.

### 4. Khoá case: sửa và chạy là hai quyền khác nhau

Hiện `can_edit` cho tester sửa khi **là người tạo hoặc được giao màn hình**. Đổi thành:

- `can_edit(user, case)`: Admin/QA Lead (là thành viên) **hoặc** tester là **người tạo**
  (`created_by`). Bỏ điều kiện "được giao màn hình" ra khỏi quyền sửa.
- `can_run(user, case)` mới: Admin/QA Lead **hoặc** tester là người tạo **hoặc** được giao màn
  hình của case.
- Quyền **tạo** case (form và nhập file) giữ nguyên: tester phải được giao màn hình.
- Chỗ dùng:
  - Sửa nội dung, đổi cách chạy, lưu trữ/ngừng dùng/khôi phục, gửi duyệt dùng `can_edit` (như
    hiện tại, chỉ đổi luật bên trong). `can_archive` vẫn dựa trên `can_edit`.
  - `POST .../manual-results` và quyền tải bằng chứng (`purpose: "evidence"`) chuyển từ
    `can_edit` sang `can_run`.
  - API chi tiết case trả thêm `can_run` (cạnh `can_edit`, `can_review`, `can_archive`), cũng
    `false` khi dự án lưu trữ.
- `mark_tested` (case Manual `DRAFT` → `TESTED` khi gửi kết quả, kèm audit `MANUAL_TEST`) chuyển
  từ `_require_edit` sang kiểm tra `can_run`. Nếu không đổi, tester chỉ chạy được sẽ gửi kết quả
  xong mà case vẫn Nháp và không có issue.
- **Tải bằng chứng:** `/media/sign` và `/media/upload` vẫn kiểm tra quyền theo **dự án** như hiện
  tại, không thêm `case_id` (*quyết định của Claude*: app dùng nội bộ, và `manual-results` đã
  kiểm tra `can_run` cùng `ensure_own_media` cho đúng case). Chỉ cần tester được giao màn hình mà
  không tạo case nào vẫn tải được bằng chứng; luật hiện tại theo vai trò và thành viên đã cho
  phép điều này.
- **Không cần duyệt:** case nhập là Manual, mà theo spec test tay case Manual không qua Duyệt,
  nên chạy ngay từ `DRAFT` được, kể cả khi dự án bật "Cần QA duyệt". Thông báo "có case mới cần
  chạy" gửi ngay lúc nhập.
- **Người tạo vẫn sửa được sau khi bị đổi màn hình:** giữ đúng như hiện tại (người tạo luôn sửa
  được case của mình).
- **Thay đổi hành vi cần biết:** tester B được giao màn hình trước đây sửa được case của tester A.
  Giờ B chỉ chạy được. Chủ dự án đã đồng ý. Ghi vào `DECISIONS.md`.
- `permissions.py`: luật tester cho `EDIT_TEST_CASE` vẫn là cờ truyền vào. Người xây chọn tách
  thành hai cờ hay thêm `Action.RUN_TEST_CASE`, miễn chỉ có một chỗ quyết định.

### 5. Bằng chứng bắt buộc khi FAIL

- `POST .../manual-results` với `status = FAIL` mà `evidence` không có video và không có ảnh nào
  (kể cả ảnh gắn ở từng bước) thì trả 422 "Kết quả Fail cần ít nhất một ảnh hoặc video bằng
  chứng". PASS/BLOCKED không bắt buộc.
- Kết quả do agent (Codex) gửi **không** đổi luật.
- `ManualRunPanel` chặn ngay ở form: chọn Fail mà chưa có bằng chứng thì nút Gửi mờ, kèm dòng
  nhắc.

### 6. Giao diện

**Trang danh sách case** (`projects/[projectId]/test-cases`): cạnh nút "Tạo case" có nút
**"Nhập từ Excel"**, hiện khi người dùng tạo được case (QA Lead/Admin, hoặc tester có ít nhất một
màn hình được giao) và dự án chưa lưu trữ. Bấm vào mở hộp thoại:

```
Nhập test case từ Excel
 1. [Tải file mẫu]   Điền theo mẫu, mỗi dòng một bước.
 2. [Chọn file .xlsx]  test-login.xlsx
 ─────────────────────────────────────────────
 Xem trước: 12 case · 41 bước · 3 màn hình
 ⚠ 1 cảnh báo   ✖ 2 lỗi
 ┌ Lỗi ───────────────────────────────────────┐
 │ Dòng 7 · Kết quả mong đợi: Không được để trống │
 │ Dòng 15 · Màn hình: Không tìm thấy "Gio hang"  │
 └────────────────────────────────────────────┘
 Mã nhóm | Màn hình  | Tiêu đề              | Số bước
 A1      | Đăng nhập | Đăng nhập đúng       | 3
 ...
                  [Chọn file khác]  [Nhập 12 case] (mờ khi còn lỗi)
```

- Chọn file xong là gọi `preview`. Còn lỗi thì nút Nhập mờ. Sửa file rồi chọn lại.
- Bấm Nhập thì gọi `import` với cùng file. Thành công thì báo "Đã nhập 12 case", đóng hộp thoại,
  tải lại danh sách. Lỗi 409/503 thì hiện câu tiếng Việt từ backend và giữ hộp thoại.
- Danh sách lỗi và cảnh báo xếp theo số dòng. Bảng xem trước cuộn được bên trong hộp thoại
  (không cuộn cả trang ở 1366×768, như các hộp thoại khác).
- Mọi chuỗi đặt ở `messages/vi.json`.

**Trang case:**
- Nút Sửa, Lưu trữ, đổi cách chạy hiện theo `can_edit` (đã có). Khung "Chạy test tay" hiện theo
  `can_run` thay cho `can_edit`.
- Khi `can_run && !can_edit`: hiện dòng nhỏ "Case do người khác viết, cần sửa hãy báo người viết
  hoặc QA Lead" (*câu chữ là quyết định của Claude*).

**Thông báo** (*quyết định của Claude*): QA Lead/Admin nhập xong thì mỗi tester được giao các
màn hình có case mới nhận **một** thông báo "Có N case mới cần chạy ở: Đăng nhập, Giỏ hàng".
Tester tự nhập thì không thông báo. Lỗi thông báo chỉ ghi log.

### 7. Thư viện

- Backend thêm `openpyxl` (đọc và tạo .xlsx) bằng `uv add openpyxl`. `python-multipart` đã có.
- Frontend không thêm thư viện: chỉ gửi file và tải file về.

## Kiểm thử (gợi ý cho người xây)

- Bộ đọc file là **hàm thuần**: nhận bytes và danh sách màn hình, trả `cases`/`errors`/`warnings`.
  Test bằng file .xlsx dựng trong test bằng `openpyxl`, không cần file mẫu thật trong repo.
- Có test cho mỗi luật ở mục 1: sai tiêu đề, nhóm không liền nhau, ô mức case mâu thuẫn, tên màn
  hình trùng, giá trị chọn sai, quá 50 bước, vượt giới hạn, dòng trống.
- Test "nhập 100 case gọi Google đúng số lần cố định" (đếm bằng gateway giả), để không vượt hạn
  mức.
- Test quyền: tester nhập màn hình không được giao, tester B không sửa được case của A nhưng chạy
  được, FAIL không có bằng chứng thì 422.

## Để lại cho người xây

- Chỗ đặt bộ đọc/tạo file (ví dụ `app/core/services/case_import.py`), tên hàm, chia task.
- Cách dịch lỗi Pydantic sang tiếng Việt (bảng ánh xạ theo loại lỗi là đủ).
- Kiểu dáng hộp thoại, dùng lại `Dialog` có sẵn.
- Cập nhật `HANDOFF.md`, `DECISIONS.md` (luật khoá mới, FAIL cần bằng chứng), tài liệu hướng dẫn
  QA cách dùng file mẫu trong `SETUP.md` hoặc `docs/`.

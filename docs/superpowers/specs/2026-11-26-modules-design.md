# Chia việc theo module — thiết kế

Ngày: 2026-11-26 · Nhánh: `feature/fun-ui` (sẽ tách nhánh `feature/modules` từ `develop`)

## Vì sao làm

Hiện QA giao việc **theo từng màn hình**. Nhưng cách tester làm việc đã đổi: tester đưa source
code của cả một phần app cho AI, AI viết ra file Excel test case có **nhiều màn hình**, rồi
tester import. Khi import, dòng nào thuộc màn hình chưa giao cho tester (hoặc màn hình chưa có
trong app) bị báo lỗi, và **cả file bị từ chối** (`check_import` trong
`backend/app/core/services/case_import.py`, `_check_file` trong `test_cases.py`).

Chủ dự án muốn QA chia việc theo **module** (một nhóm màn hình, ví dụ "Tài khoản" gồm Đăng
nhập, Quên mật khẩu, Đổi mật khẩu). Tester nhận module, đưa module đó cho AI, rồi import file.
Import không còn báo lỗi vì màn hình.

## Mục tiêu

1. QA Lead/Admin tạo, sửa, xoá **module** trong dự án. Mỗi màn hình thuộc **tối đa một** module.
2. QA **giao cả module** cho một hoặc nhiều tester, kèm deadline.
3. Tester **tự nhận** module. Nếu module đã có người làm, tester thấy **cảnh báo đỏ** "X đang
   làm module này", nhưng **vẫn nhận được** (tester 1 có thể nhờ tester 2 làm giúp).
4. Khi import, người nhập **chọn một module**. Cột "Màn hình" trong file được so tên với các
   màn hình **trong module đó** (không phân biệt hoa/thường, bỏ khoảng trắng thừa, chuẩn hoá
   Unicode NFC như `_find_screen` hiện có):
   - Trùng tên: thêm case vào màn hình đó.
   - Chưa có: **tự tạo màn hình mới trong module** (chỉ tên, các trường khác để trống), rồi
     thêm case. Bước xem trước chỉ báo "Sẽ tạo mới N màn hình: …", **không phải lỗi**.
5. Màn hình mới tạo khi import được **tự giao cho người nhập** (nếu là tester), nên không còn
   lỗi "màn hình chưa được giao".

## Không làm (đợt này)

- Module lồng nhau (module con).
- Một màn hình thuộc nhiều module.
- Cột "Module" trong file Excel: module chọn trong hộp thoại import, mẫu Excel giữ nguyên.
- Đổi cách tính trạng thái việc, trang Kết quả, trang "Việc của tôi": các trang này vẫn chạy theo
  việc giao từng màn hình như hôm nay.
- Deadline riêng cho module: deadline vẫn nằm ở từng dòng giao việc của màn hình.

## Chống mục tiêu (làm thế này là hỏng)

- Import vẫn từ chối cả file chỉ vì một tên màn hình chưa có.
- Import tạo màn hình "ma" rồi lỗi ở bước ghi case: màn hình mới đã ghi nhưng không có case.
  (Chấp nhận được nếu hiếm, nhưng không được để người dùng nhập lại sinh màn hình trùng tên.)
- Tester tự nhận được module rồi sửa case của người khác. Quy tắc khoá theo người tạo giữ nguyên.
- Cảnh báo "đang có người làm" lại **chặn** việc nhận.
- Giao một module 20 màn hình tốn 20+ lượt ghi Google Sheets (hạn mức khoảng 60 lượt/phút).
- Dữ liệu cũ (màn hình chưa có module, việc giao theo màn hình) bị mất hoặc không dùng được.

## Các cách đã xét

- **Cách 1 — Module giữ việc giao.** Bảng giao việc chuyển từ màn hình sang module, màn hình thừa
  hưởng. Dữ liệu gọn, nhưng phải sửa mọi chỗ đang đọc `Assignment.screen_id` (quyền sửa/chạy
  case, trang Kết quả, "Việc của tôi", trạng thái việc, thông báo, xoá màn hình/thành viên) và
  chuyển dữ liệu cũ. Rủi ro cao.
- **Cách 2 — Giữ việc giao theo màn hình, module là lớp gom nhóm (đã chọn).** "Giao/nhận module"
  = tạo việc giao cho **mọi màn hình** trong module, ghi một lượt. "Ai đang làm module" = những
  người có việc giao ở ít nhất một màn hình của module. Code quyền và kết quả hiện có chạy tiếp.
  Đổi lại: dữ liệu lặp (một tester × N màn hình), và màn hình mới thêm vào module phải tự giao
  cho người đang làm module.
- Cách 3 — Không có module, chỉ cho import tự tạo và tự giao màn hình. Rẻ nhất nhưng QA không chia
  việc theo nhóm được, không có cảnh báo "đang có người làm". Bỏ.

Bổ sung sau khi viết (quyết định của Claude): cách 2 thuần không giao được **module rỗng**, mà
đây lại là trường hợp chính (QA tạo module, giao, rồi tester import mới sinh màn hình). Nên thêm
một tab nhỏ `ModuleAssignments` lưu "ai đang làm module". Việc giao theo màn hình vẫn được tạo
tự động từ tab này, nên phần quyền/kết quả hiện có vẫn không phải sửa.

Chủ dự án chọn: chia việc kiểu **kết hợp** (QA giao + tester tự nhận, chỉ cảnh báo không chặn),
**cách 2**, và **chọn module trong hộp thoại import, màn hình chưa có thì tự tạo**.

## Thiết kế

### Dữ liệu (Sheet riêng của dự án)

- Tab mới `Modules`: `id` (dạng `MD-0001`, dùng `IdGenerator` như màn hình), `name`,
  `description`, `created_at`. Tên module không trùng trong dự án (so như tên màn hình).
- Tab `Screens` thêm cột `module_id` ở cuối (rỗng = "Chưa phân module").
  `_ensure_tabs` / `upgrade_project_spreadsheets` đã tự thêm tab và cột còn thiếu cho dự án cũ.
- Tab mới `ModuleAssignments`: `id`, `module_id`, `assignee_email`, `deadline`, `created_at`.
  Đây là nguồn duy nhất cho câu hỏi "ai đang làm module". Cần bảng này vì QA thường tạo và giao
  module **khi nó còn rỗng** (màn hình chỉ xuất hiện sau khi tester import), mà việc giao theo
  màn hình không lưu được cho module rỗng (đây là quyết định của Claude, xem "Các cách đã xét").
- Tab `Assignments` **không đổi**. Việc giao theo màn hình vẫn là thứ quyết định quyền và kết
  quả; nó được **tự tạo** từ `ModuleAssignments`.
- Trong một module, tên màn hình không trùng. Giữa hai module thì được trùng.

### Quyền

| Việc | Ai làm được |
|---|---|
| Tạo/sửa/xoá module, chuyển màn hình vào module | QA Lead, Admin (`MANAGE_SCREENS`) |
| Giao module cho tester bất kỳ | QA Lead, Admin |
| Tự nhận module | Tester là thành viên dự án |
| Bỏ nhận module của chính mình | Tester đó |
| Bỏ giao module của người khác | QA Lead, Admin |
| Import vào một module | QA Lead/Admin: mọi module. Tester: module mình đang làm |

Người được giao vẫn phải là tester đang hoạt động và là thành viên (`_check_assignee`).

### Giao / nhận / bỏ module

"Người đang làm module" = các dòng `ModuleAssignments` của module đó.

- **Giao module** (QA): chọn tester + deadline. Tạo một dòng `ModuleAssignments` cho mỗi tester
  chưa làm module này (đã làm thì bỏ qua, như `assign` hiện có). Đồng thời, với mỗi màn hình
  đang có trong module mà tester chưa có việc, tạo một dòng `Assignment` cùng deadline (trạng
  thái tính như `assign` hiện có). Mọi dòng mới ghi **một lượt mỗi tab** (thêm `create_many`
  cho hai repository, giống `TestCaseRepository.create_many`). Module rỗng vẫn giao được: chỉ
  tạo dòng `ModuleAssignments`. Mỗi tester nhận **một** thông báo cho cả module.
- **Tự nhận** (tester): như giao module cho chính mình. Deadline: tester chọn, mặc định là
  deadline xa nhất của người đang làm module đó, nếu chưa ai làm thì hôm nay + 7 ngày.
- **Đổi deadline module**: sửa dòng `ModuleAssignments` và mọi `Assignment` của tester đó trong
  module.
- **Bỏ nhận / bỏ giao module**: xoá dòng `ModuleAssignments` và mọi việc giao của tester đó ở
  các màn hình trong module. Case tester đã viết **giữ nguyên**.
- **Màn hình mới vào module** (QA tạo trong module, chuyển màn hình vào module, hoặc import tạo
  mới): tự tạo `Assignment` cho **mọi người đang làm module**, deadline lấy từ dòng
  `ModuleAssignments` của người đó.
- **Chuyển màn hình ra khỏi module**: việc giao hiện có giữ nguyên (không tự xoá).
- Giao một màn hình lẻ như hôm nay (trang màn hình → "Giao việc") **vẫn dùng được**, không
  đụng tới `ModuleAssignments`.

### Cảnh báo "đang có người làm"

Module hiện danh sách người đang làm (tên + deadline). Khi tester mở hộp thoại "Nhận module" mà
module đã có người khác làm, hộp thoại hiện dòng đỏ: "Tester 1 đang làm module này. Bạn vẫn có
thể nhận để làm cùng." Nút "Nhận" vẫn bấm được. Backend không chặn.

### Import theo module

Hộp thoại import (`frontend/components/test-cases/import-dialog.tsx`) thêm ô **chọn module**
(bắt buộc). Tester chỉ thấy module mình đang làm; QA thấy mọi module.

Backend (`preview_import` / `import_cases` nhận thêm `module_id`):

1. Màn hình để so khớp = các màn hình có `module_id` đó. Mã màn hình (`SC-0001`) vẫn dùng được,
   nhưng nếu mã thuộc module khác thì báo lỗi dòng: "Màn hình SC-0001 thuộc module khác".
2. Tên chưa có → đưa vào danh sách "màn hình sẽ tạo". Các dòng cùng tên mới gom về một màn hình.
3. Kiểm tra quyền: QA bỏ qua. Tester phải đang làm module (có dòng `ModuleAssignments`), nếu
   không thì từ chối cả lần nhập với câu "Hãy nhận module trước khi nhập". Màn hình đã có trong
   module mà tester **chưa** được giao (ví dụ QA giao màn hình lẻ cho người khác) thì tự giao cho
   tester khi import, không báo lỗi. Màn hình mới tạo thì giao cho mọi người đang làm module.
4. Xem trước trả thêm `new_screens: list[str]`. Giao diện hiện "Sẽ tạo mới N màn hình: …".
5. Bấm nhập: giữ khoá theo thứ tự **screens → assignments → test-cases**, đọc và kiểm tra lại
   file trong khoá, rồi ghi: màn hình mới (một lượt, `ScreenRepository.create_many`), việc giao
   mới (một lượt), case (một lượt như hiện nay). Ghi màn hình hoặc việc giao lỗi → chưa ghi case,
   trả lỗi "Google Sheets đang bận". Ghi case lỗi sau khi đã tạo màn hình → màn hình rỗng còn lại;
   lần nhập lại sẽ **khớp tên** với màn hình đó nên không sinh trùng.
6. Màn hình tạo tự động ghi AuditLog `CREATE` với `actor` là người nhập.

Mọi thứ khác của import (gom dòng theo "Mã nhóm", báo lỗi theo dòng, trùng tiêu đề, khoá theo
người tạo, thông báo gộp) giữ nguyên.

### Giao diện

Trang **Màn hình** gom theo module:

```
Màn hình                                   [+ Module]  [+ Màn hình]
▾ Tài khoản (3 màn hình)   Đang làm: An (30/11), Bình (02/12)   [Giao] [Nhận]
    Đăng nhập · Quên mật khẩu · Đăng ký
▾ Giỏ hàng (2 màn hình)    Chưa ai làm                          [Giao] [Nhận]
    Giỏ hàng · Thanh toán
▾ Chưa phân module (4)
    ...
```

- "Giao" chỉ hiện với QA, "Nhận"/"Bỏ nhận" chỉ hiện với tester.
- Form màn hình (`screen-form-dialog.tsx`) thêm ô chọn module.
- Trang **Giao việc** giữ nguyên danh sách việc theo màn hình (đây là dữ liệu thật), thêm cột
  hoặc nhóm theo module để dễ nhìn.
- Chữ mới thêm vào cả `vi` và `en` của next-intl.

### Xoá

- Xoá module: chỉ khi module **không còn màn hình**. Các dòng `ModuleAssignments` của nó xoá theo.
- Xoá màn hình: luật hiện có giữ nguyên.

## Quyết định của Claude sau bước đọc lại (chủ dự án kiểm tra)

1. **Import không theo module.** Ô chọn module có thêm lựa chọn "Không theo module (như cũ)",
   chạy đúng luồng `_check_file` hôm nay: so khớp mọi màn hình, tester chỉ nhập vào màn hình được
   giao, không tự tạo màn hình. Nhờ vậy dữ liệu cũ và tester chỉ có việc giao lẻ vẫn import được.
   QA và tester có việc giao lẻ thấy lựa chọn này.
2. **Bỏ nhận / đổi deadline module đụng mọi việc giao của tester đó trong module**, kể cả việc QA
   giao lẻ trước đó. Không thêm cột đánh dấu vào `Assignments`. Hộp thoại xác nhận ghi rõ "Sẽ bỏ
   N việc giao màn hình trong module". Case đã viết giữ nguyên.
3. **Bỏ thành viên khỏi dự án** xoá luôn các dòng `ModuleAssignments` của người đó (luật chặn
   theo `Assignments` hiện có giữ nguyên). Khi tự giao màn hình mới, bỏ qua người không còn là
   tester đang hoạt động của dự án, không báo lỗi cả lần nhập.
4. **Xoá màn hình trong module**: nếu màn hình **không có case nào**, cho xoá và xoá luôn các
   việc giao của nó (thường là việc tự tạo, hoặc màn hình rỗng còn lại sau import lỗi). Còn case
   thì luật cũ giữ nguyên. Màn hình không thuộc module nào: luật cũ giữ nguyên.
5. **Tên trùng ở dự án cũ**: luật "không trùng tên trong module" chỉ kiểm khi tạo, đổi tên, hoặc
   chuyển màn hình vào module. Chuyển một màn hình vào module đã có tên đó thì bị từ chối kèm
   câu báo rõ. Dữ liệu cũ không bị sửa.
6. **Khoá**: `ScreenRepository` cần có `lock()` công khai và `create_many` không tự lấy khoá lần
   nữa (giống `TestCaseRepository`), nếu không thì import tự chặn chính nó và báo 409.
   `ModuleAssignments` dùng chung khoá với `Assignments` cho đơn giản.

## Việc còn để người làm quyết

1. Cách hiện tên/deadline trong danh sách "Đang làm" (tối đa bao nhiêu người, rút gọn thế nào).
2. Mã lỗi HTTP cụ thể cho từng trường hợp, theo kiểu router hiện có (422 dữ liệu sai, 403 quyền,
   409 khoá bận).

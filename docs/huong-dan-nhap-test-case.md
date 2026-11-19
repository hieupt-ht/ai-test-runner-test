# Hướng dẫn nhập test case từ file Excel

Dành cho QA Lead, Admin và tester. Thay vì tạo từng case bằng form, bạn viết cả bộ test case trong Excel theo mẫu rồi nhập vào app một lần.

## 1. Tải file mẫu

1. Vào dự án, mở trang **Test case**.
2. Bấm nút **Nhập từ Excel** (cạnh nút Tạo case).
3. Trong hộp thoại, bấm link **Tải file mẫu**. Bạn nhận file `mau-test-case.xlsx`.

Nút "Nhập từ Excel" chỉ hiện khi bạn tạo được case và dự án chưa lưu trữ.

File mẫu có hai sheet:

- `Test case`: điền dữ liệu vào đây. Dòng 1 là tiêu đề cột, dữ liệu bắt đầu từ dòng 2. Đã có một case ví dụ 3 bước (dòng 2-4): **xoá nó trước khi nhập**, nếu không nó sẽ được nhập như case thật.
- `Hướng dẫn`: tóm tắt luật ngay trong file. App không đọc sheet này.

Bạn có thể soạn trong Google Sheets rồi tải về dạng `.xlsx`.

## 2. Ý nghĩa 16 cột

Giữ nguyên dòng 1: không đổi chữ, không đổi thứ tự, không xoá cột. Cột thừa bên phải cột 16 sẽ bị bỏ qua.

| # | Cột | Bắt buộc | Ý nghĩa |
|---|---|---|---|
| 1 | Mã nhóm | Có | Chữ bất kỳ (A1, A2...) để gom các dòng thành một case |
| 2 | Màn hình | Có | Tên màn hình trong dự án (hoặc mã màn hình, ví dụ SC-0001) |
| 3 | Mã yêu cầu | | Mã yêu cầu/user story liên quan |
| 4 | Tiêu đề | Có | Tên case (tối đa 200 ký tự) |
| 5 | Điều kiện trước | | Cần có gì trước khi test |
| 6 | Dữ liệu test | | Dữ liệu dùng khi test |
| 7 | Điểm bắt đầu | | Bắt đầu test từ đâu (trang, màn hình...) |
| 8 | Bước làm | Có (mỗi dòng) | Một bước thao tác |
| 9 | Mong đợi của bước | | Kết quả mong đợi của riêng bước đó |
| 10 | Kết quả mong đợi | Có | Kết quả cuối cùng của cả case |
| 11 | Điều kiện sau | | Trạng thái sau khi test xong |
| 12 | Mức độ | Có | LOW, MEDIUM hoặc HIGH |
| 13 | Ưu tiên | Có | P1, P2 hoặc P3 |
| 14 | Nền tảng | | WEB, ANDROID hoặc IOS. Để trống là WEB |
| 15 | Loại test | | FUNCTIONAL hoặc UI. Để trống là FUNCTIONAL |
| 16 | Regression | | Có hoặc Không. Để trống là Không (nhận thêm Yes/No, TRUE/FALSE, x) |

Các cột 12 đến 16 có danh sách chọn sẵn trong file mẫu, không phân biệt chữ hoa chữ thường. Mỗi case tối đa 50 bước.

## 3. Luật gom dòng

- **Mỗi dòng là một bước.** Các dòng cùng "Mã nhóm" gom thành một case, bước theo thứ tự từ trên xuống.
- Thông tin của case (màn hình, tiêu đề, mức độ...) ghi ở **dòng đầu** của nhóm. Ở các dòng sau, để trống hoặc ghi giống hệt dòng đầu. Ghi khác đi thì app báo lỗi (thường là do gõ nhầm Mã nhóm).
- Các dòng của một nhóm phải **nằm liền nhau**. Đừng để nhóm A1 xuất hiện lại sau nhóm A2.
- Dòng có dữ liệu thì phải có "Mã nhóm". Dòng trống hoàn toàn thì được bỏ qua.

## 4. Ví dụ nhỏ

Một case "Đăng nhập" 3 bước và một case khác 1 bước:

| Mã nhóm | Màn hình | Tiêu đề | Bước làm | Mong đợi của bước | Kết quả mong đợi | Mức độ | Ưu tiên |
|---|---|---|---|---|---|---|---|
| A1 | Đăng nhập | Đăng nhập thành công bằng email hợp lệ | Mở trang đăng nhập | Thấy form đăng nhập | Người dùng vào được trang chủ | HIGH | P1 |
| A1 | | | Nhập email và mật khẩu đúng | | | | |
| A1 | | | Bấm nút Đăng nhập | Chuyển sang trang chủ | | | |
| A2 | Đăng nhập | Đăng nhập sai mật khẩu | Nhập mật khẩu sai rồi bấm Đăng nhập | Báo sai mật khẩu | Vẫn ở trang đăng nhập | MEDIUM | P2 |

(Các cột khác để trống hoặc điền nếu cần.)

## 5. Giới hạn

- Chỉ nhận file `.xlsx`.
- Tối đa 2 MB, 2000 dòng dữ liệu, 300 case mỗi lần. File lớn hơn thì chia nhỏ.

## 6. Các bước nhập trong app

1. Bấm **Nhập từ Excel**, chọn file `.xlsx`.
2. App **xem trước** ngay: số case, số bước, danh sách case, cảnh báo và lỗi theo từng dòng.
3. Còn lỗi thì nút nhập bị mờ. Sửa file xong, chọn lại file ở ô **File Excel** (hộp thoại tự xem trước lại).
4. Hết lỗi thì bấm **Nhập N case**. App tạo tất cả case cùng lúc. File còn lỗi thì **không nhập case nào**, nên không sợ nhập được một nửa.

Cảnh báo (ví dụ "Màn hình Đăng nhập đã có case cùng tiêu đề") không chặn việc nhập. Nó nhắc bạn có thể đang nhập lại file cũ. Nhập lại file đã nhập sẽ tạo case trùng, vì lần nhập nào cũng chỉ tạo case mới, không sửa case cũ.

## 7. Lỗi hay gặp và cách sửa

| Thông báo | Nguyên nhân | Cách sửa |
|---|---|---|
| File không đúng mẫu, hãy tải file mẫu mới. Cột này phải là "..." | Dòng 1 bị đổi chữ, đổi thứ tự hoặc thiếu cột | Dùng lại tiêu đề của file mẫu |
| Không đọc được file .xlsx | File hỏng hoặc không phải .xlsx (ví dụ .xls, .csv) | Lưu lại thành .xlsx |
| File quá lớn, tối đa 2 MB | Vượt 2 MB | Chia nhỏ file |
| File có quá 2000 dòng dữ liệu | Quá nhiều dòng | Chia nhỏ file |
| File có quá 300 test case, hãy chia nhỏ file | Quá nhiều case | Chia nhỏ file |
| File không có test case nào | File chỉ có tiêu đề | Điền dữ liệu từ dòng 2 |
| Không được để trống | Thiếu ô bắt buộc | Điền ô đó (xem cột "Bắt buộc" ở mục 2) |
| Không tìm thấy màn hình này trong dự án | Tên màn hình sai chính tả hoặc chưa có | Sửa tên cho đúng, hoặc nhờ QA Lead tạo màn hình trước. App không tự tạo màn hình |
| Có nhiều màn hình tên này, hãy ghi mã màn hình | Hai màn hình trùng tên | Ghi mã màn hình (ví dụ SC-0001) thay cho tên |
| Bạn chưa được giao màn hình này | Tester nhập vào màn hình không được giao | Nhờ QA Lead giao màn hình, hoặc bỏ case đó khỏi file |
| Các dòng của một nhóm phải nằm liền nhau | Nhóm bị tách ra bởi nhóm khác | Dồn các dòng cùng nhóm lại gần nhau |
| Khác với dòng đầu của nhóm | Ô thông tin case ở dòng sau khác dòng đầu | Xoá ô đó hoặc sửa cho giống dòng đầu; kiểm tra có gõ nhầm Mã nhóm không |
| Giá trị không hợp lệ, hãy chọn một trong: ... | Mức độ, Ưu tiên, Nền tảng hoặc Loại test sai | Chọn từ danh sách |
| Giá trị không hợp lệ, hãy ghi Có hoặc Không | Ô Regression sai | Ghi Có hoặc Không |
| Quá 50 bước / Quá N ký tự | Case quá dài | Rút gọn hoặc tách thành case khác |

Lỗi nào cũng kèm số dòng trong Excel (dòng tiêu đề là dòng 1) và tên cột.

Ngoài ra, app có thể báo: "Có người đang tạo case, hãy thử lại" (có người khác đang ghi, chờ một chút) hoặc "Google Sheets đang bận, chưa nhập case nào, hãy thử lại" (chưa có case nào được nhập, bấm nhập lại được).

## 8. Ai nhập được vào màn hình nào

| Vai trò | Nhập được vào |
|---|---|
| Admin, QA Lead | Mọi màn hình của dự án |
| Tester | Chỉ các màn hình **được giao cho mình** |

## 9. Sau khi nhập, tester làm gì

Case nhập vào có đặc điểm: test tay (Manual), trạng thái **Nháp**, phiên bản 1, không cần duyệt, chưa có ảnh/video (QA Lead/Admin hoặc người tạo case vào app gắn thêm).

- Khi QA Lead/Admin nhập, mỗi tester được giao màn hình có case mới nhận một thông báo "Có N case mới cần chạy ở: ...". Tester tự nhập thì không có thông báo.
- Tester mở case và dùng khung **Chạy test tay**: tick từng bước, chọn **Pass** hoặc **Fail**, ghi lý do nếu lỗi, rồi gửi kết quả.
- Chọn **Fail** thì **bắt buộc** có ít nhất một ảnh hoặc video bằng chứng. Chưa có thì nút Gửi bị mờ.
- Tester **không sửa được** case do người khác viết (QA Lead, Admin hay tester khác), chỉ chạy được. Trang case sẽ ghi "Case do người khác viết, cần sửa hãy báo người viết hoặc QA Lead". Tester chỉ sửa được case do chính mình tạo.
- Trạng thái việc của màn hình tính trên mọi case chưa ngừng dùng của màn hình đó, ai tạo cũng tính. Trạng thái "Đang viết" nay hiển thị là **"Đang làm"**.

# Thiết kế: Bằng chứng ảnh/video, test app mobile, giao bug cho dev

Ngày: 2026-11-16. Nhánh nền: `feature/ai-agent-runner`.

## 1. Vì sao làm

Chủ dự án đã demo app cho sếp. Sếp chưa ưng vì:

- Giao diện chưa ổn. Trang tạo test case hẹp (`max-w-3xl`), hai bên trống, phải cuộn nhiều.
- Thiếu bằng chứng. Sếp muốn mở một kết quả là **thấy được lỗi sai, có ảnh, có video**. Hiện mỗi kết quả chỉ có tối đa một link ảnh. Codex lưu ảnh trên máy nên trường `evidence` gần như luôn trống (việc dở số 2 trong HANDOFF).

Ngoài ra dự án cần:

- Test cả **app mobile (Android và iOS)**, không chỉ web.
- Codex hay **nhận nhầm giao diện**, nên tester phải **chỉ đường bằng ảnh/video**: màn hình nào, bấm nút nào, sẽ sang màn hình nào.
- Khi case FAIL phải biết **dev nào phụ trách** phần đó và giao bug cho dev đó.
- Bỏ bước QA duyệt: tester gửi là lên issue luôn.

Thước đo thành công: sếp mở trang Kết quả của một case FAIL và thấy được bước nào sai, ảnh của bước đó, video cả lần chạy, môi trường chạy và dev được giao, mà không cần hỏi thêm ai.

## 2. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu**

1. Case có thêm thông tin: nền tảng, loại test, regression, điểm bắt đầu, ảnh/video chỉ đường theo bước và theo cả case.
2. Tester upload ảnh/video lên Cloudinary ngay trong form, xem trước được.
3. Codex (web, Android, iOS) đẩy ảnh từng bước và video lên Cloudinary và gửi kết quả theo từng bước.
4. Trang Kết quả hiển thị kết quả từng bước, ảnh, video, môi trường và dev phụ trách.
5. Test app Android (máy Windows) và iOS (máy Mac) bằng Maestro MCP.
6. Mỗi màn hình có dev phụ trách. Case FAIL thì app gán issue cho dev đó trên GitHub.
7. Công tắc "Cần QA duyệt" theo dự án, mặc định **tắt**.
8. Sửa case đã gửi thì cập nhật thẳng lên issue và có lịch sử phiên bản.
9. Chạy cả bộ regression cho một bản build.
10. Trang tạo/sửa case chia 2 cột, không cuộn cả trang trên màn hình laptop.

**Không làm đợt này**

- Vai trò Dev và trang "Bug của tôi". Dev chỉ đọc issue trên GitHub.
- Test Security, sheet RTM, Defect Log, Test Summary.
- Thiết bị đám mây (BrowserStack...), giả lập Android (dùng điện thoại thật trước).
- App tự mở Codex. Người vẫn mở Codex bằng prompt như hiện nay.
- Codex "xem video". Codex không đọc được video; xem mục 5.3.

**Phản mục tiêu (làm thì coi như hỏng dù chạy được)**

- Khoá bí mật Cloudinary nằm ngoài backend (trên máy Codex, trong frontend, trong issue).
- Hai máy Codex chạy trùng cùng một issue.
- Sửa case thì sinh case hoặc issue mới bị trùng.
- Issue của repo công khai chứa `test_data` hoặc email (quy ước hiện có vẫn giữ).
- Thêm sheet mới làm tăng số lượt đọc Google Sheets (hạn mức khoảng 60 lượt/phút).

## 3. Ràng buộc

- Dữ liệu chính vẫn ở Google Sheets. Chỉ backend ghi Sheet qua repository; chỉ `gateway.py` gọi Google.
- Codex chạy **ngoài** app: đọc issue qua GitHub MCP, gửi kết quả qua API agent (`AGENT_API_TOKEN`). App comment và đổi nhãn bằng GitHub App.
- Hai máy chạy Codex: **Windows** (web + Android, điện thoại Android thật cắm USB) và **Mac** (iOS, giả lập trong Xcode).
- Cloudinary gói miễn phí: giới hạn dung lượng file video và tổng dung lượng. Người làm cần kiểm tra con số hiện hành khi cài đặt.
- TDD, Conventional Commits, comment tiếng Việt, chuỗi giao diện ở `frontend/messages/vi.json`.

## 4. Các cách đã cân nhắc

### 4.1 Đưa ảnh/video lên Cloudinary

| Cách | Mô tả | Được | Mất |
|---|---|---|---|
| A. App làm trung gian | Tester và Codex gửi file cho backend, backend đẩy lên Cloudinary | Đơn giản, khoá chỉ ở backend | Video lớn đi qua backend hai lần |
| **B. App cấp chữ ký upload (đã chọn)** | Backend ký một yêu cầu upload có hạn ngắn. Trình duyệt/Codex đẩy thẳng lên Cloudinary rồi báo link về app | Khoá chỉ ở backend, video không qua backend, tester và Codex dùng chung một luồng | Thêm một bước; Codex cần script nhỏ |
| C. Codex giữ khoá | Codex tự upload bằng khoá riêng | Nhanh cho Codex | Khoá nằm trên 2 máy; hai luồng khác nhau |

Chủ dự án chọn **B**.

### 4.2 Cách test iOS

Ban đầu cân nhắc thiết bị đám mây (BrowserStack), thuê Mac đám mây và iOS chạy tay. Chủ dự án có **Mac và điện thoại Android**, nên iOS chạy tự động trên Mac.

### 4.3 Chạy Codex trên mấy máy

| Cách | Được | Mất |
|---|---|---|
| Tất cả trên Mac | Một máy, cài một lần | Mac phải luôn sẵn sàng |
| **Chia hai máy (đã chọn, tạm thời)** | Dùng máy Windows sẵn có cho web + Android | Phải chia việc theo nhãn |

### 4.4 Lưu kết quả từng bước

| Cách | Được | Mất |
|---|---|---|
| Sheet `StepResults` mới | Giống Xray, dễ lọc trong Sheet | Thêm lượt đọc Sheet |
| **Cột JSON trong `Results` (đã chọn, đề xuất của Claude)** | Không thêm lượt đọc; link ngắn nên ô đủ chứa | Khó lọc bằng tay trong Sheet |

### 4.5 Công cụ điều khiển mobile

Cân nhắc Maestro MCP, Appium MCP, Codex Android MCP/mobile-mcp. Chọn **Maestro MCP**: chạy cả Android và iOS, bấm theo chữ trên màn hình nên ít nhầm nút, không cần Appium server.

### 4.6 Regression

Chọn tách `test_type` (chọn 1) và `regression` (bật/tắt) thay vì để Regression là một loại trong `test_type`, vì một case có thể vừa là Chức năng vừa thuộc bộ regression.

## 5. Thiết kế đã chốt

### 5.1 Dữ liệu (Google Sheets)

Không thêm sheet mới. Chỉ thêm cột vào cuối các sheet hiện có. Dòng cũ thiếu cột mới thì đọc ra giá trị mặc định.

**`Projects`** (tab chung)

| Cột mới | Mặc định | Ghi chú |
|---|---|---|
| `android_app_id` | rỗng | ví dụ `com.shop.app` |
| `ios_bundle_id` | rỗng | ví dụ `com.shop.app` |
| `require_review` | `false` | công tắc "Cần QA duyệt" |

**`Screens`**

| Cột mới | Mặc định | Ghi chú |
|---|---|---|
| `dev_owner` | rỗng | GitHub username của dev phụ trách, không có `@` |

**`TestCases`**

| Cột | Mặc định | Ghi chú |
|---|---|---|
| `steps` (mở rộng) | | Mỗi bước thêm `guide_media: Media[]` (tối đa 5 mục mỗi bước) |
| `platform` (mới) | `WEB` | `WEB` / `ANDROID` / `IOS` |
| `test_type` (mới) | `FUNCTIONAL` | `FUNCTIONAL` / `UI` |
| `regression` (mới) | `false` | |
| `start_point` (mới) | rỗng | URL/đường dẫn hoặc tên màn hình. Rỗng thì dùng `route` của màn hình |
| `guide_media_json` (mới) | `[]` | ảnh/video cho cả case (tối đa 5 mục) |
| `postcondition` (mới) | rỗng | không bắt buộc |
| `requirement_ref` (mới) | rỗng | không bắt buộc |

**`Runs`**

| Cột | Ghi chú |
|---|---|
| `scope` (mở rộng) | thêm `regression_only: bool` |
| `build_version` (mới) | ví dụ `v1.4.2`; một đợt chạy cùng một bản build |

**`Results`**

| Cột | Ghi chú |
|---|---|
| `evidence_json` (mở rộng) | `{"video": Media \| null, "screenshots": Media[]}`. Dòng cũ dạng `{"screenshot": "..."}` vẫn đọc được |
| `step_results_json` (mới) | `[{step_no, status, actual, screenshot: Media \| null}]` |
| `actual_result` (mới) | tóm tắt điều thực tế xảy ra |
| `environment` (mới) | ví dụ `Chrome 131 / Windows 11`, `Pixel 7 / Android 14`, `iPhone 15 Simulator / iOS 18` |
| `executed_by` (mới) | `codex-windows` hoặc `codex-mac`. Đợt này không có kết quả nhập tay nên không có email *(quyết định của Claude)* |
| `case_version` (mới) | phiên bản case lúc chạy |
| `dev_owner` (mới) | `dev_owner` của màn hình **lúc ghi kết quả**, để lịch sử đúng khi sau này đổi người phụ trách *(quyết định của Claude)* |
| `defect_url` (mới) | không bắt buộc |

**Kiểu `Media`** (lưu dạng JSON):

```json
{"kind": "image" | "video", "url": "https://res.cloudinary.com/<cloud>/...", "public_id": "...", "note": ""}
```

Backend chỉ nhận `url` thuộc đúng `res.cloudinary.com/<CLOUDINARY_CLOUD_NAME>/`. Link khác bị từ chối kèm lỗi tiếng Việt.

### 5.2 Upload (cách B)

1. Client (trình duyệt hoặc script của Codex) gọi backend xin chữ ký: `POST /api/projects/{project_id}/media/sign` (người dùng đã đăng nhập) hoặc `POST /api/agent/projects/{project_id}/media/sign` (token agent). Gửi kèm `kind` (`image`/`video`).
2. Backend trả `{cloud_name, api_key, timestamp, signature, folder, public_id}`. `folder` theo mẫu `ai-test-runner/<project_id>/<guide|evidence>/...`. `public_id` do backend sinh ngẫu nhiên, khó đoán. **`api_secret` không bao giờ rời backend.**
3. Client upload thẳng lên Cloudinary và nhận `secure_url`.
4. Client gửi `Media` kèm dữ liệu case hoặc kết quả. Backend kiểm tra domain/cloud name trước khi ghi Sheet.

Cấu hình mới trong `.env`: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`. Không in, không commit.

Giới hạn do app đặt: ảnh tối đa 10MB, video tối đa 100MB và 3 phút (đề xuất; điều chỉnh theo gói Cloudinary). Chỉ nhận định dạng ảnh/video phổ biến.

**Dọn file trên Cloudinary** (chủ dự án chọn cách C):
- Tester xoá hoặc thay ảnh/video hướng dẫn rồi lưu case: backend xoá file cũ trên Cloudinary theo `public_id`. File có trong lịch sử phiên bản cũ cũng bị xoá, lịch sử chỉ giữ chữ.
- Bằng chứng của Codex: mỗi case chỉ giữ file của **5 lần chạy gần nhất**. Khi ghi kết quả thứ 6, backend xoá ảnh/video của kết quả cũ nhất trên Cloudinary. Dòng kết quả trong Sheet vẫn giữ, trang Kết quả hiện "Bằng chứng đã được dọn".
- Xoá chạy nền; lỗi xoá thì ghi log, không làm hỏng việc lưu case hay ghi kết quả.
- File đã ký upload nhưng không gắn vào đâu (tester bỏ dở): đợt này không dọn. Ghi nhận là việc sau.

### 5.3 Codex và video

Codex đọc được ảnh, **không đọc được video**. Khi render issue, với mỗi video hướng dẫn, app tạo thêm vài link **ảnh cắt từ video** bằng phép biến đổi URL của Cloudinary (lấy khung hình tại giây 1, 3, 5...; tối đa 6 ảnh). Các link này tạo khi cần, không lưu Sheet. Video gốc vẫn để người xem.

### 5.4 Issue và chia máy

- Nội dung issue thêm: nền tảng, loại test, điểm bắt đầu, `android_app_id`/`ios_bundle_id` khi cần, link ảnh hướng dẫn theo bước, ảnh cắt từ video.
- Nhãn mới: `platform: web`, `platform: android`, `platform: ios`.
- Prompt Codex trên Windows chỉ lấy issue có `platform: web` hoặc `platform: android`; trên Mac chỉ lấy `platform: ios`. Viết lại `docs/codex-agent.md` thành hai prompt và hai phần hướng dẫn cài đặt.
- Chống chạy trùng *(quyết định của Claude)*: nhãn nền tảng tách hai máy. Trên mỗi máy chỉ mở **một phiên Codex** một lúc (ghi rõ trong `docs/codex-agent.md`). Đợt này không thêm cơ chế giữ chỗ. Nếu một case đổi `platform` khi đang chạy, kết quả vẫn được nhận; lần sửa đó đã gắn `needs-rerun` (5.8) nên case sẽ được chạy lại trên đúng máy.
- Ảnh trong issue repo công khai: link Cloudinary có `public_id` ngẫu nhiên. Tester được nhắc không chụp thông tin nhạy cảm (một dòng nhắc trong form).

### 5.5 Kết quả từ Codex

API `POST /api/agent/projects/{project_id}/results` nhận thêm: `step_results`, `evidence` (dạng mới), `actual_result`, `environment`, `executed_by`, `build_version` (tuỳ chọn, ghi vào Run nếu Run chưa có). Vẫn nhận `evidence` dạng chuỗi cũ để không làm hỏng prompt đang dùng.

Codex phải:
- chụp ảnh **mỗi bước** (pass hay fail), upload qua cách B;
- quay video cả lần chạy: web bằng Playwright `recordVideo`, Android bằng `adb shell screenrecord`, iOS bằng `xcrun simctl io booted recordVideo`;
- gửi `case_version` bằng số phiên bản ghi trong issue.

Comment của app trên issue thêm: bảng từng bước (✅/❌), link ảnh bước lỗi, link video.

### 5.6 Giao bug cho dev

- Trang Màn hình thêm ô **Dev phụ trách** (GitHub username). QA Lead/Admin sửa được.
- Khi nhận kết quả **FAIL**: nếu màn hình có `dev_owner`, app gán issue cho người đó (GitHub assignees), gắn nhãn `bug: cần sửa` và nhắc `@<dev_owner>` trong comment kết quả.
- Khi kết quả mới là **PASS**: app bỏ nhãn `bug: cần sửa` (giữ nguyên người được gán để còn lịch sử).
- Dev sửa xong: comment trên issue; QA Lead bấm **Chạy lại** như hiện nay.
- Gán thất bại (username sai, không có quyền repo) thì không làm hỏng việc ghi kết quả; chỉ ghi log và thêm dòng cảnh báo vào comment.

### 5.7 Bỏ bước duyệt

- `require_review = false` (mặc định): thao tác **Gửi** chuyển `DRAFT → APPROVED`, tạo issue và ghi Sheet ngay. Nút **Duyệt/Trả lại** và **Duyệt hàng loạt** của QA Lead vẫn hiện nhưng mờ, có tooltip "Dự án đang tắt bước duyệt". API trả 409 nếu bị gọi.
- `require_review = true`: luồng cũ như hiện nay.
- Công tắc nằm trong trang Cài đặt dự án (Admin/QA Lead).
- Khi tắt công tắc, các case đang `IN_REVIEW` của dự án được chuyển sang `APPROVED` một lần, có ghi AuditLog. Trạng thái đổi ngay trong một lượt ghi Sheet. Issue được tạo **chạy nền** qua `BackgroundIssueSync` sẵn có (một luồng, không gọi GitHub dồn dập). Tạo issue lỗi thì không hoàn tác trạng thái; QA Lead bấm **Đồng bộ lại issue** như hiện nay *(quyết định của Claude)*.
- Thông báo "có case chờ duyệt" không gửi khi công tắc tắt.

### 5.8 Sửa case đã gửi

Khi `require_review = false` và case đang `APPROVED`/`TESTED`:

- Lưu thay đổi giữ nguyên trạng thái (không về `DRAFT`), tăng `version`, ghi AuditLog với diff (như hiện có).
- App cập nhật nội dung issue và thêm comment "📝 Case đã sửa lên v<N>: <tóm tắt trường thay đổi>".
- Nếu đổi `steps`, `expected_result`, `start_point`, `platform` hoặc ảnh/video hướng dẫn **và** case đã từng có kết quả: gắn `needs-rerun` (dùng lại luồng Chạy lại).
- Trang chi tiết case có mục **Lịch sử** (đọc AuditLog): phiên bản, thời gian (giờ Việt Nam), người sửa, các trường đổi.
- Trang Kết quả ghi "chạy với v<N>" cho mỗi kết quả.

Khi `require_review = true`, giữ hành vi cũ (sửa thì về `DRAFT`).

### 5.9 Regression

- Form case có ô **Regression**.
- Trang Kết quả (QA Lead/Admin) có nút **Chạy bộ regression**. Bấm vào thì hiện hộp thoại nhập bản build. App tạo một Run (`regression_only = true`, `build_version`) và gắn `needs-rerun` cho mọi case `regression = true`, `APPROVED`/`TESTED`, kèm comment ghi mã Run.
- Trang Kết quả lọc được theo Run và theo "chỉ regression".

**Gắn kết quả vào Run regression** *(quyết định của Claude)*:
- Comment "Yêu cầu chạy lại" của app ghi rõ mã Run (ví dụ `RUN-0007`). API kết quả của agent nhận thêm `run_id` (tuỳ chọn). Có `run_id` thì kết quả vào Run đó và `total/passed/failed` được cộng dồn. Không có thì giữ hành vi cũ: mỗi lần POST tạo một Run mới.
- Run regression ở trạng thái `RUNNING` nhưng **không** chặn các lần ghi kết quả khác. Quy tắc "đang có Run `QUEUED`/`RUNNING` thì từ chối" chỉ áp dụng cho Run thường.
- Run regression tự chuyển `COMPLETED` khi mọi case trong Run đã có kết quả. QA Lead cũng có thể bấm **Kết thúc** (case chưa chạy giữ là chưa có kết quả).

**Trạng thái `TESTED`** *(quyết định của Claude)*: hiện chưa có code nào đặt `TESTED` và API agent chỉ nhận case `APPROVED`. Đợt này giữ nguyên như vậy, không thêm chuyển trạng thái sang `TESTED`. Các chỗ ghi "`APPROVED`/`TESTED`" trong thiết kế hiểu là `APPROVED`.

### 5.10 Giao diện

**Trang tạo/sửa case** bỏ `max-w-3xl`, dùng gần hết chiều rộng, chia 2 cột từ màn hình `lg` trở lên:

```
┌───────────────────────────────────────────────────────────────────────┐
│ ← Quay lại   Tạo test case                     [Huỷ] [Lưu nháp] [Gửi]│
├─────────────────────────────┬─────────────────────────────────────────┤
│ THÔNG TIN                   │ CÁC BƯỚC                       [+ Bước] │
│ Tiêu đề [_______________]   │ ┌─1─ Bấm nút giỏ hàng ────────────────┐ │
│ Màn hình [▾]  Nền tảng [▾]  │ │ Mong đợi: mở trang Giỏ hàng         │ │
│ Loại [▾]      ☑ Regression  │ │ [ảnh][ảnh][+]                       │ │
│ Ưu tiên [▾]   Mức độ [▾]    │ └─────────────────────────────────────┘ │
│ Bắt đầu tại [__________]    │  (chỉ khung này cuộn khi nhiều bước)    │
│ ▸ Điều kiện, dữ liệu, ...   │ Kết quả mong đợi cuối [______________]  │
│ 🎬 Video cả case [▶][+]     │                                         │
└─────────────────────────────┴─────────────────────────────────────────┘
```

- Thanh nút cố định trên cùng.
- Ô dài ít dùng (điều kiện, dữ liệu, postcondition, mã yêu cầu) nằm trong mục thu gọn.
- Ảnh hiện thumbnail ngay sau upload, bấm để phóng to. Video có trình phát, tua được. Đang upload thì có thanh tiến độ. Mỗi mục có nút xoá.
- Dưới `lg` thì xếp một cột.
- Một dòng nhắc: "Đừng chụp mật khẩu hoặc thông tin cá nhân; ảnh có thể hiện trong issue công khai."

**Trang Kết quả**: bấm một kết quả mở bảng chi tiết bên phải (hoặc toàn màn hình trên điện thoại):

```
TC-000005 Thêm vào giỏ hàng        ❌ FAIL · v2 · Pixel 7 / Android 14
Dev phụ trách: @nguyenvana · Issue #12 · Chạy bởi codex-windows
───────────────────────────────────────────────────────────────
▶ [Video cả lần chạy]
Bước  Trạng thái  Thực tế                         Ảnh
1     ✅          Mở trang chủ                     [ảnh]
2     ❌          Không thấy nút "Thêm vào giỏ"     [ảnh]
3     –           Không chạy
Mong đợi: ...            Thực tế: ...
```

Trang Kết quả cũng được chỉnh cho đồng bộ (đã có commit style trước), thêm bộ lọc nền tảng, Run, regression.

### 5.11 Cài đặt máy chạy (tài liệu, không phải code)

- **Windows:** Java 17+, Android Platform Tools (`adb`), Maestro CLI, Maestro MCP gắn vào Codex, điện thoại Android bật Gỡ lỗi USB. Playwright như hiện có.
- **Mac:** Xcode + iOS Simulator, Java 17+, Maestro CLI, Maestro MCP. Bản build iOS cho Simulator (`.app`) do dev cung cấp.
- Cả hai: script `upload_evidence` (Python, đặt trong repo, ví dụ `tools/agent/upload_evidence.py`) gọi API ký rồi upload và in ra JSON `Media`. Script đọc `AGENT_API_TOKEN` từ biến môi trường.

## 6. Thứ tự làm đề xuất

1. Dữ liệu và mô hình: cột mới, đọc dòng cũ không lỗi, `Media`, kiểm tra domain Cloudinary.
2. Công tắc duyệt + sửa case đã gửi + lịch sử.
3. Upload Cloudinary (ký, frontend upload, xem trước) + form 2 cột.
4. Issue: nội dung mới, nhãn nền tảng, ảnh cắt từ video.
5. API kết quả mở rộng + script `upload_evidence` + trang Kết quả mới.
6. Dev phụ trách + gán issue khi FAIL.
7. Regression run.
8. Tài liệu cài Windows/Mac, prompt Codex cho 2 máy; chạy thử thật web, Android, iOS.

## 7. Để lại cho người làm

- Tên endpoint, tên component và cách chia file cụ thể.
- Thư viện upload phía frontend (gọi `fetch`/`XMLHttpRequest` để có tiến độ là đủ).
- Thời điểm cắt khung hình video và số ảnh, trong giới hạn ở 5.3.
- Kiểm tra lại giới hạn dung lượng gói Cloudinary hiện hành và điều chỉnh giới hạn ở 5.2.
- Cách hiển thị lịch sử (danh sách hay dòng thời gian).

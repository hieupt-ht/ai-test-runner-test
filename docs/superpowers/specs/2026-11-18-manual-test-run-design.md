# Test tay (Manual) và chọn cách chạy cho test case — thiết kế

Ngày: 2026-11-18 · Nhánh: `feature/ai-agent-runner`

## Vì sao làm

Codex chạy Android đang trục trặc, nhưng dự án vẫn cần test. Tester đã tự viết case
(form case có sẵn) nhưng **chưa có chỗ nào để tự chạy tay và báo kết quả**: hiện chỉ
agent (Codex, qua token `AGENT_API_TOKEN`) mới ghi được tab `Results`.

Luồng tester muốn (lời chủ dự án): viết case cho màn hình (ví dụ Đăng nhập: nhập tài khoản,
mật khẩu…), đính ảnh màn hình đang làm, chạy xong thì báo kết quả; có bug thì ghi cụ thể và
giao cho người sửa; issue GitHub được giao rồi thì dev vào xem và sửa.

## Mục tiêu

1. Mỗi test case có **cách chạy**: `MANUAL` (mặc định khi tạo mới) hoặc `AUTOMATION`.
2. Case Manual: tester tự chạy tay, tick từng bước, ghi thực tế, đính ảnh/video bằng chứng,
   chọn Pass/Fail cho cả case, chọn người sửa khi Fail.
3. Kết quả tay đi chung đường với kết quả của agent: tab `Runs`/`Results`, trang Kết quả,
   comment trên issue GitHub, nhãn pass/fail/bug, giao issue cho dev.
4. Trạng thái case Manual **không** dùng "Chờ duyệt/Đã duyệt".

## Không làm (đợt này)

- Phần Automation mới (agent vẫn chạy như cũ, chỉ là chỉ nhặt case Automation).
- QA Lead duyệt/“cần sửa” case Manual (có thể thêm sau).
- Chạy tay nhiều case một lúc (mỗi lần gửi là một case).
- Regression run cho case Manual: bộ regression chỉ gồm case Automation.

## Chống mục tiêu (làm thế này là hỏng)

- Case Manual hiện trên issue như case chờ Codex chạy → Codex chạy nhầm.
- Tester phải đợi duyệt mới được chạy case mình viết.
- Ảnh bằng chứng sai kho vẫn lưu được, hoặc file ảnh bị dọn nhầm.
- Kết quả tay ghi đè/mất kết quả của agent.

## Các cách đã xét

- **A. Dùng chung `Runs`/`Results` (đã chọn).** Gửi kết quả tay tạo một Run đã hoàn tất
  (`triggered_by` = email tester), ghi một `Result` y như agent. Trang Kết quả, issue,
  nhãn, giao dev dùng lại được. Phải gỡ vài chỗ đang giả định "kết quả chỉ do agent ghi".
- B. Tab `ManualResults` riêng: không đụng agent nhưng phải làm lại issue, trang kết quả,
  thống kê, sau này lại phải gộp. Bỏ.
- C. Chỉ tick Pass/Fail trên case, issue tự tạo bằng tay: không có bước/bằng chứng/giao
  người sửa. Bỏ.

## Thiết kế

### 1. Trường "cách chạy"

- `TestCaseContent.execution_mode: ExecutionMode` với `ExecutionMode = MANUAL | AUTOMATION`.
- Cột mới `execution_mode` nối vào **cuối** `TEST_CASE_COLUMNS`.
- Case mới (API và form) mặc định `MANUAL`.
- **Ô trống ở Sheet cũ đọc thành `AUTOMATION`** (case cũ đều viết cho agent). Đây là
  quyết định của Claude; chủ dự án đã đồng ý.
- Form case: chọn bằng hai nút (Manual / Automation) ở đầu form; chọn Automation hiện ghi
  chú “Agent sẽ chạy sau khi case được duyệt”.
- Danh sách case: có cột/nhãn cách chạy và bộ lọc theo cách chạy.
- `execution_mode` là trường nội dung (có trong lịch sử sửa, nhãn tiếng Việt "Cách chạy").

### 2. Trạng thái case Manual

```
Nháp ──(tester gửi kết quả)──► Đã kiểm thử  [Pass]/[Fail]
  ▲                                 │
  └────────(sửa nội dung case)──────┘
```

- Case Manual **không** có thao tác Gửi duyệt / Duyệt / Trả về. Từ `DRAFT` gửi kết quả
  **PASS hoặc FAIL** là sang `TESTED`. Gửi lại kết quả khi đang `TESTED` thì vẫn `TESTED`.
- Gửi **BLOCKED** (chưa chạy được, ví dụ môi trường hỏng) chỉ ghi kết quả, **không đổi
  trạng thái** và không tạo/đổi issue. *(Quyết định của Claude: BLOCKED nghĩa là chưa test
  xong, nên không được tính "Đã kiểm thử".)*
- Sửa nội dung case `TESTED` (có đổi thật) → về `DRAFT`. Không tạo yêu cầu "chạy lại"
  trên issue cho case Manual (yêu cầu đó là tín hiệu cho Codex).
- Đổi cách chạy:
  - Manual → Automation: case về `DRAFT`, đi luồng duyệt như cũ.
  - Automation → Manual: case về `DRAFT`.
- Lưu trữ (`ARCHIVE`) đã cho phép từ `TESTED`; ngừng dùng (`DEPRECATE`) thêm phép từ
  `TESTED` cho case Manual. Hành vi khác giữ nguyên.
- Nhãn trạng thái hiển thị cạnh **Pass/Fail của kết quả gần nhất** (lấy từ `Results`).
- Việc được giao (`Assignments`, hàm thuần `derive_assignment_status`, không đọc thêm
  `Results`): còn case `DRAFT` → "Đang viết"; còn `IN_REVIEW` → "Chờ duyệt"; **mọi** case
  (bỏ `DEPRECATED`) đều là Manual `TESTED` → "Đã test"; còn lại (có case Automation
  `APPROVED`) → "Đã duyệt" như cũ. *(Quyết định của Claude: luật cũ của Automation chưa
  bao giờ ra "Đã test" vì không đọc `Results`; giữ nguyên để không tốn thêm lượt đọc Sheet.
  Màn hình trộn Manual + Automation vì vậy dừng ở "Đã duyệt".)*

### 3. Gửi kết quả tay (backend)

`POST /api/projects/{project_id}/test-cases/{case_id}/manual-results`, người dùng đăng nhập
thường (không phải token agent).

- Quyền: người được sửa case (`service.can_edit` — tester tạo case và được giao màn hình,
  QA Lead/Admin). Dự án lưu trữ → 409. Case không phải Manual, hoặc ở trạng thái khác
  `DRAFT`/`TESTED` → 409 kèm câu tiếng Việt.
- Body: `status` (`PASS`/`FAIL`/`BLOCKED`), `step_results` (mỗi bước: `PASS`/`FAIL`/`SKIPPED`,
  `actual`, ảnh tuỳ chọn), `actual_result`, `reason` (mô tả lỗi; **bắt buộc khi FAIL**),
  `failed_step` (bắt buộc khi FAIL, phải là bước có thật), `evidence` (video + tối đa 20 ảnh),
  `environment` (bắt buộc, ví dụ "Chrome 130 / Windows 11"), `build_version` (tuỳ chọn),
  `assignee` (tên GitHub, tuỳ chọn), `version` (phiên bản case tester đang xem).
- `version` khác phiên bản hiện tại → 409 "Case vừa được sửa, hãy tải lại" (không ghi).
- Kiểm tra mọi ảnh/video thuộc kho của mình (`ensure_own_media`) → sai thì 422.
- **Thư mục bằng chứng:** người dùng đăng nhập được tải lên với `purpose: "evidence"`
  (cùng thư mục bằng chứng agent dùng) khi có quyền sửa case. Với Cloudinary, backend
  chặn ảnh/video bằng chứng không nằm trong thư mục bằng chứng của **đúng dự án** (kiểm tra
  tiền tố `public_id`) → 422, nên ảnh hướng dẫn không bị dùng làm bằng chứng rồi bị dọn nhầm.
  Với Drive chỉ kiểm tra dạng link như hiện tại. *(Quyết định của Claude: app dùng nội bộ,
  chủ dự án không cần ràng buộc chặt; chặn Drive theo thư mục phải gọi thêm Drive API.)*
- Ghi: tạo Run `COMPLETED`, `total=1`, `triggered_by` = email tester, `scope.case_ids=[case_id]`,
  rồi một `Result` với `executed_by` = email tester, `case_version` = version,
  `dev_owner` = `assignee` nếu có, không thì dev phụ trách màn hình.
- Đổi case sang `TESTED` (nếu đang `DRAFT`), có ghi lịch sử.
- Đang có run khác chưa xong (`RunInProgressError`) hoặc khoá bận → 409 "thử lại".
- Sheet lỗi khi ghi Result → Run đánh `FAILED`, trả 503 (giống agent).
- Sau khi ghi: dùng lại logic của agent — thông báo cho Admin/QA Lead (và người tạo case khi
  FAIL), đồng bộ issue (dưới đây). Lỗi GitHub/thông báo chỉ ghi log, không làm hỏng request.
- Phần chung với agent (dựng `Result`, đếm, thông báo, đồng bộ issue) tách thành một hàm
  dùng chung; người xây chọn chỗ đặt.

### 4. Issue GitHub cho case Manual

- Hiện issue chỉ được tạo khi case `APPROVED`. Thêm: case Manual được tạo issue khi
  sang `TESTED` (lần gửi kết quả đầu), rồi comment kết quả như agent.
- Issue case Manual có nhãn `mode: manual`. Nhãn này là nhãn do app sinh: đổi case sang
  Automation thì app gỡ nó đi (không để `_merge_labels` giữ lại); nhãn trạng thái là `status:TESTED`, nên prompt
  Codex hiện tại (lọc `status:APPROVED` hoặc `needs-rerun`) tự bỏ qua. Cập nhật
  `docs/codex-agent.md`: luôn bỏ qua issue có nhãn `mode: manual`.
- FAIL: giao issue cho `dev_owner` của Result, gắn nhãn bug, comment có bảng bước và ảnh
  bước lỗi (logic sẵn có). PASS: đóng issue, gỡ nhãn bug (logic sẵn có). BLOCKED: chỉ ghi
  kết quả, không đổi issue (như agent).
- Comment ghi người chạy là tester (email không đưa lên repo công khai — theo luật
  `_safe_text` hiện có; hiện tên hiển thị/“Tester” thay cho email).

### 5. Giao diện

- **Form case**: nút chọn cách chạy (mục 1).
- **Trang case** (Manual, người có quyền, dự án chưa lưu trữ): khung **"Chạy test tay"**:

```
Chạy test tay                          Môi trường: [Chrome 130 / Windows 11]
 B1 Mở /login              ○ Đạt ○ Không đạt ○ Bỏ qua   Thực tế: [......]  [ảnh]
 B2 Nhập sai mật khẩu      ○ Đạt ● Không đạt ○ Bỏ qua   Thực tế: [......]  [ảnh]
 Kết quả thực tế: [..........]       Bằng chứng: [video/ảnh — dán, kéo thả, tải lên]
 Kết quả cả case:  ○ Pass  ● Fail  ○ Blocked     Mô tả lỗi: [........]
 Giao cho (GitHub): [nguyenvana]   ← mặc định dev phụ trách màn hình
 [Gửi kết quả]
```

  - Phải chọn kết quả cho **mọi** bước mới gửi được (backend cũng kiểm tra đủ số bước).
  - Nhãn Pass/Fail gần nhất chỉ hiện khi case đang `TESTED`.
  - Chọn "Không đạt" ở một bước thì gợi ý Fail và điền `failed_step` = bước đầu tiên
    Không đạt; tester vẫn đổi được.
  - Dùng `MediaPicker` sẵn có (tôn trọng kho Cloudinary/Drive của dự án); khoá nút Gửi khi
    đang tải ảnh.
  - Nhớ ô "Môi trường" lần trước ở trình duyệt (tiện, không bắt buộc).
  - Gửi xong: báo thành công, làm mới case/kết quả; khung hiện "Lần chạy gần nhất: Fail ·
    RUN-xxxx · <giờ>" kèm link sang trang Kết quả.
- **Trang Kết quả**: kết quả tay hiện như kết quả agent; cột người chạy hiện email tester
  (trong app được xem email).
- Case Automation: trang case giữ nguyên nút Gửi duyệt/Duyệt.
- Chuỗi tiếng Việt thêm vào `messages/vi.json`.

### 6. Sheet và dữ liệu

- Chỉ thêm một cột: `TestCases.execution_mode`. `Runs`/`Results` đủ cột (đã có
  `step_results_json`, `actual_result`, `environment`, `executed_by`, `case_version`,
  `dev_owner`, `evidence_json`, `build_version`). Sheet cũ được nâng cấp khi khởi động /
  bỏ lưu trữ (cơ chế sẵn có).
- Agent (`POST .../agent/results`) **bỏ qua case Manual** với lý do "Case test tay".
  Regression run chỉ lấy case Automation.
- Bằng chứng của kết quả tay theo luật giữ 5 lần chạy gần nhất mỗi case (sẵn có).

## Để lại cho người xây

- Tên component, chỗ đặt hàm dùng chung giữa agent và kết quả tay.
- Cách hiện nhãn Pass/Fail gần nhất trên danh sách case mà không vượt hạn mức đọc Sheet
  (~60 lần/phút): ưu tiên dùng lại dữ liệu kết quả đã tải, không gọi thêm mỗi dòng.
- Cách chia đợt (ví dụ: đợt 1 backend, đợt 2 frontend).

## Ràng buộc

- TDD, comment tiếng Việt, Conventional Commits nội dung tiếng Việt; chạy cả hai bộ test.
- Cột Sheet mới luôn nối vào cuối.
- Next.js 16: `useParams/useSearchParams` trong `<Suspense>`; sinh lại API bằng `npm run gen:api`.
- Không push/PR khi chưa được đồng ý.

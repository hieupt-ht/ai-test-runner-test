# Thiết kế: Giao diện vui hơn cho tester (màu, đồ thị, nhím bug, xếp hạng, nhạc)

Ngày: 2026-11-19 · Trạng thái: chờ chủ dự án duyệt

## 1. Ý định và lý do

Tester dùng app hằng ngày và thấy nó "khô khan": chỉ có hai chế độ sáng/tối đơn sắc, trang
tổng quan chỉ có vài thẻ số. Chủ dự án muốn app **vui và có màu hơn** để tester đỡ nhàm chán,
có động lực viết case và bắt bug: thêm một giao diện màu mè, đồ thị, một con nhím "pet" lớn
lên theo số bug mình bắt được, bảng xếp hạng trong team, và nút bật nhạc.

## 2. Mục tiêu, không làm, và điều phải tránh

**Mục tiêu**
1. Thêm giao diện thứ 3 **"Kẹo ngọt"** (pastel). Giữ nguyên Sáng và Tối.
2. Trang **Tổng quan chung** có đồ thị; thêm trang **Tổng quan project** mới (tab đầu tiên).
3. Mỗi người có **một con nhím riêng**: lớn theo số bug bắt được, biểu cảm theo chuỗi ngày làm việc.
4. **Bảng xếp hạng theo từng project**: viết nhiều case nhất, bắt nhiều bug nhất.
5. **Nút phát nhạc** lofi trên thanh đầu trang.

**Không làm (lần này)**
- Bảng xếp hạng gộp toàn hệ thống.
- Phần thưởng, huy hiệu, cửa hàng đồ cho nhím, thông báo "nhím đói".
- Lưu riêng điểm game (xem mục Cách làm).

**Điều phải tránh (làm xong mà dính thì coi như hỏng)**
- App chậm đi rõ rệt: mở trang tổng quan phải đọc lại Google Sheets mỗi lần.
- Có chỗ không đổi màu khi đổi giao diện (chữ trắng trên nền trắng, đồ thị giữ màu cũ…).
- Nhạc tự phát khi mở trang.
- Biến trò chơi thành áp lực/kiểm soát. Chủ dự án muốn **tin nhau, vui vẻ**: chỉ chặn trùng ở
  mức nhẹ (mục 6.5), không có cơ chế duyệt điểm hay phạt.

## 3. Ràng buộc

- Frontend Next.js 16 (đọc `frontend/AGENTS.md` trước khi viết route), Tailwind 4, shadcn,
  `next-themes` (`attribute="class"`), react-query, next-intl (chuỗi tiếng Việt trong `messages/vi.json`).
- Backend FastAPI, dữ liệu ở Google Sheets (đọc chậm, vài trăm ms mỗi bảng), đã có
  `GenerationCache` trên Redis (`backend/app/core/cache.py`).
- Quyền: tester bình thường **không** xem được kết quả chi tiết của người khác. API mới chỉ
  trả **số đếm** và tên, không lộ nội dung kết quả.
- TDD, comment tiếng Việt, code dễ đọc cho sinh viên.

## 4. Các cách đã cân nhắc

| Cách | Mô tả | Được | Mất |
|---|---|---|---|
| **1. Backend tính từ dữ liệu có sẵn + cache Redis** ✅ | API mới đọc test case và kết quả, đếm ra số liệu, lưu cache; xoá cache khi có case/kết quả mới | Không thêm bảng; số luôn đúng vì tính từ gốc; dùng lại `GenerationCache` | Lần đầu (chưa có cache) chậm ~1s |
| 2. Sheet "điểm game" riêng | Cộng điểm mỗi khi có sự kiện | Đọc rất nhanh | Hai nơi phải khớp; xoá/sửa case dễ làm điểm lệch |
| 3. Frontend tự đếm | Tải danh sách về rồi đếm | Không sửa backend | Chậm khi dữ liệu nhiều; tester không được xem kết quả người khác nên không làm được xếp hạng |

**Chủ dự án chọn cách 1.**

## 5. Những gì chủ dự án đã quyết

- Nhím **của từng người**, có cho **mọi vai trò** (Tester, QA Lead, Admin, Viewer cùng đua).
- Kiểu nhím: **C – "Bóng bẩy"** (gradient tím, má hồng, có ánh sáng). Mẫu SVG tham khảo:
  `.superpowers/brainstorm/694-1795094950/content/nhim-style.html` (không commit; người làm
  có thể chép lại hình vẽ từ đó).
- 4 biểu cảm: **Cười, Bình thường, Đói, Khóc**.
- Bảng xếp hạng **theo từng project**.
- Giao diện thứ 3: **A – "Kẹo ngọt"**. Bảng màu tham khảo (mẫu `theme-3.html`):
  nền `#FFF7FB`, thẻ `#FFFFFF`, chữ `#3A2350`, chữ phụ `#9C7FB0`, màu nhấn `#B15CFF`,
  đồ thị `#C4A1FF` / `#FF9FCB` / `#8BE3C9`, viền `#F3DDF0`, thanh bên `#FBE9F7`.
- Sáng và Tối **giữ nguyên**; khi đổi chế độ **mọi thứ phải đổi màu theo**.
- Chống gian lận: **tin nhau** – chỉ giới hạn nhẹ "1 bug cho mỗi phiên bản case" (mục 6.5),
  không có nút "không tính", không bắt buộc người thứ hai xác nhận.

## 6. Thiết kế

### 6.1 Giao diện thứ 3 "Kẹo ngọt"
- Thêm lớp `.candy` trong `frontend/app/globals.css`, khai báo lại **toàn bộ** biến màu như
  `:root`/`.dark` đang có (background, card, primary, muted, border, sidebar-*, chart-1..5…).
- `ThemeProvider`: `themes={["light", "dark", "candy"]}`; menu trong `topbar.tsx` thêm mục
  "Kẹo ngọt". "Theo hệ thống" giữ như cũ.
- Quy tắc: component mới **chỉ dùng biến màu** (`bg-card`, `text-muted-foreground`,
  `var(--chart-1)`…), không viết mã màu cứng. Ngoại lệ duy nhất: thân con nhím giữ màu tím riêng
  của nó; khung quanh nhím dùng biến màu.
- Đồ thị đọc màu từ `var(--chart-n)` nên tự đổi theo giao diện.

### 6.2 Đồ thị (thư viện Recharts)
**Tổng quan chung** (`app/(app)/page.tsx`), giữ các thẻ hiện có theo vai trò, thêm:
- Thẻ **Nhím của tôi** + chuỗi ngày (mọi vai trò).
- **Tiến độ từng project** (thanh ngang: case "xong" / tổng case) – cho các project người đó là thành viên.
  "Xong" = APPROVED hoặc TESTED (case tay đi thẳng DRAFT → TESTED, không qua APPROVED).
  "Tổng" = mọi case trừ ARCHIVED và DEPRECATED. *(người viết spec tự quyết)*
- **Kết quả 14 ngày** gộp các project người đó thấy (cột chồng): Pass, Fail, và **Khác**
  (BLOCKED + INCONCLUSIVE, màu xám).

**Tổng quan project** (route mới `app/(app)/projects/[projectId]/overview/page.tsx`):
- `projects/[projectId]/page.tsx` chuyển hướng sang `/overview` thay vì `/screens`; thêm tab
  "Tổng quan" đứng đầu thanh tab của project.
- 3 thẻ số: tổng case, % Pass (lần chạy gần nhất mỗi case), số bug đang mở.
- Cột Pass/Fail theo ngày (14 ngày).
- Vòng tròn trạng thái case: Nháp / Chờ duyệt / Đã duyệt (+ Đã test).
- Tiến độ theo màn hình (thanh ngang).
- 2 bảng xếp hạng (mục 6.4).

### 6.3 Con nhím và chuỗi ngày
- **Cấp** theo tổng số bug người đó bắt được trong các project **đang là thành viên**
  (Admin: mọi project chưa bị xoá). Không đọc project cũ để tránh chậm. *(người viết spec tự quyết)*

  | Số bug | Cấp |
  |---|---|
  | 0–4 | Nhím con |
  | 5–19 | Nhím nhỡ |
  | 20–49 | Nhím trưởng thành |
  | 50+ | Vua nhím (đội vương miện) |

  Kích thước SVG tăng theo cấp; có thanh "còn X bug nữa lên cấp".
- **Ngày làm việc** = ngày (giờ Việt Nam) người đó viết ít nhất 1 case hoặc ghi ít nhất 1 kết quả.
  **Chuỗi** = số ngày làm việc liên tiếp tính đến hôm nay, **chỉ xét thứ 2–6**:
  - Bỏ **1 ngày thứ 2–6** là gãy chuỗi (về 0).
  - **Hôm nay chưa làm thì chưa tính là bỏ** (chuỗi vẫn giữ số của hôm qua).
  - Cuối tuần không làm không ảnh hưởng; có làm thì vẫn được cộng vào chuỗi.
  - Ví dụ: làm thứ 6, mở app sáng thứ 2 chưa làm gì → chuỗi vẫn còn, số ngày bỏ = 0.
- **Số ngày bỏ** = số ngày thứ 2–6 đã qua (không tính hôm nay) kể từ lần làm việc gần nhất.
- **Biểu cảm**:
  - Cười: hôm nay đã bắt được bug.
  - Bình thường: hôm nay đã làm việc, hoặc số ngày bỏ = 0.
  - Đói: số ngày bỏ = 1–2 (chuỗi đã gãy, nhím đòi ăn).
  - Khóc: số ngày bỏ ≥ 3.
  - Chưa từng làm việc: Bình thường (nhím con mới nở).
  *(người viết spec tự quyết, chủ dự án có thể sửa)*
- Nhím là một component React vẽ SVG thuần (`components/pet/hedgehog.tsx`), nhận `level`, `mood`.
  Có hoạt ảnh CSS nhẹ (nhún nhảy, chớp mắt) và tắt khi người dùng bật `prefers-reduced-motion`.

### 6.4 Bảng xếp hạng (theo project)
- Hai bảng: **Viết case** và **Bắt bug**. Lọc: **Tuần này / Tháng này / Tất cả**.
- Hiện top 5 và dòng của chính mình (nếu ngoài top 5).
- **Viết case**: đếm case do người đó tạo (`created_by`) đang ở trạng thái Đã duyệt hoặc Đã test
  (bỏ Nháp, Chờ duyệt, Lưu trữ, Ngừng dùng). Thời gian lọc theo `created_at` của case.
  Case tay tự viết tự chạy (DRAFT → TESTED, không qua duyệt) **vẫn được tính** – tin nhau.
- "Tuần này" = từ thứ 2 tuần hiện tại, "Tháng này" = từ ngày 1, theo giờ Việt Nam.
- **Bắt bug**: xem 6.5.

### 6.5 Thế nào là "bắt được 1 bug"
- Một kết quả **FAIL** được tính cho:
  - kết quả chạy tay: người chạy (`executed_by`, là email);
  - kết quả do agent chạy (`executed_by` là tên máy, ví dụ `codex-windows`): người viết case (`created_by`).
  - Phân biệt hai loại: `executed_by` có chứa "@" là người, không có là agent.
- Người chạy là chính tác giả case **vẫn được tính** (tin nhau).
- **Giới hạn nhẹ chống trùng: mỗi case tối đa 1 bug cho mỗi phiên bản case** (`case_version`).
  Chạy lại nhiều lần, đổi qua lại PASS/FAIL trên cùng phiên bản thì vẫn chỉ 1 bug. Case được sửa
  sang phiên bản mới và lại FAIL thì tính thêm 1. Kết quả cũ không có `case_version` coi như cùng một phiên bản.
- Bug được tính cho người của **kết quả FAIL đầu tiên** của phiên bản đó, vào ngày của kết quả đó
  (dùng cho lọc tuần/tháng và chuỗi "hôm nay bắt được bug").
- BLOCKED và INCONCLUSIVE không ảnh hưởng gì đến việc đếm bug.
- "Bug đang mở" (thẻ số project) = số case (chưa lưu trữ/ngừng dùng) mà kết quả PASS/FAIL gần nhất là FAIL.
- % Pass (thẻ số project) = trong các case có kết quả PASS/FAIL, tỉ lệ case có kết quả gần nhất là PASS.

### 6.6 API mới (backend)
| API | Trả về | Ai gọi được |
|---|---|---|
| `GET /me/pet` | cấp, tổng bug, số bug để lên cấp, chuỗi, biểu cảm | mọi người đăng nhập |
| `GET /me/dashboard` | tiến độ từng project + Pass/Fail 14 ngày của các project mình thấy | mọi người đăng nhập |
| `GET /projects/{id}/stats` | thẻ số, Pass/Fail theo ngày, trạng thái case, tiến độ theo màn hình | thành viên project / Admin |
| `GET /projects/{id}/leaderboard?period=week\|month\|all` | 2 bảng: tên, email, số đếm, thứ hạng | thành viên project / Admin |

- Phần tính toán viết thành **hàm thuần** trong `backend/app/core/services/stats.py` (nhận danh
  sách case + kết quả, trả số liệu), để test dễ, không cần Sheets.
- Cache: dùng `GenerationCache` theo project (TTL ~10 phút). Xoá cache project khi tạo/sửa/duyệt
  case, nhập case từ Excel, hoặc ghi kết quả (tay hoặc agent) của project đó. `/me/pet` ghép từ
  cache số liệu của từng project người đó là thành viên (mỗi cache project lưu sẵn số đếm theo từng người).
- Chạy `npm run gen:api` để cập nhật kiểu cho frontend.

### 6.7 Nút nhạc
- Nút ▶/⏸ trong `topbar.tsx`. Dùng một thẻ `<audio>` đặt ở layout `(app)` nên chuyển trang không ngắt nhạc.
- Không tự phát. Nhớ "đang bật/tắt" và âm lượng trong `localStorage` (bọc try/catch).
  Khi tải lại trang chỉ nhớ trạng thái, người dùng bấm lại mới phát (trình duyệt chặn tự phát).
- 2–3 bài lofi **miễn phí bản quyền**, để trong `frontend/public/music/`, nhấn nút "bài tiếp".

### 6.8 Hiệu năng
- Thêm cho trình duyệt: Recharts (~100KB nén), nhím là SVG nhỏ, nhạc chỉ tải khi bấm phát (`preload="none"`).
- Trang đồ thị tải Recharts kiểu động (`next/dynamic`) để không làm chậm các trang khác.
- Số liệu lấy từ cache Redis; chỉ lần đầu hoặc sau khi có thay đổi mới đọc Sheets.

## 7. Chia đợt (mỗi đợt làm xong, test xanh mới sang đợt sau)
1. Giao diện "Kẹo ngọt" + rà mọi màn hình hiện có để đổi màu đúng.
2. Backend: hàm tính số liệu + 4 API + cache.
3. Trang Tổng quan project + đồ thị ở Tổng quan chung.
4. Nhím + chuỗi ngày.
5. Bảng xếp hạng.
6. Nút nhạc.

## 8. Để người làm tự quyết
- Bố cục chi tiết của từng trang (lưới, khoảng cách), miễn là ổn ở bề ngang điện thoại.
- Hình vẽ chi tiết của 4 cấp nhím (vương miện, gai dài hơn…) dựa trên kiểu C.
- Màu cụ thể cho `.candy` ngoài bảng ở mục 5, và màu chart-4/chart-5.
- Tên hàm, tên file, cách chia component.
- Chọn bài nhạc cụ thể (phải ghi nguồn và giấy phép trong `frontend/public/music/LICENSE.md`).

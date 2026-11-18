# Dùng Codex chạy test case từ GitHub issue (hai máy: Windows và Mac)

Luồng: Tester bấm **Gửi** case trên AI Test Runner (nếu dự án tắt "Cần QA duyệt" thì case được duyệt luôn; nếu bật thì QA Lead duyệt trước) → app tạo issue trong repo của dự án → bạn tự mở Codex để chạy test → Codex đẩy ảnh/video lên Cloudinary rồi gọi API ghi kết quả vào tab `Results` của Google Sheet → **app tự comment kết quả lên issue**, đóng/mở issue, đổi nhãn và giao bug cho dev. App không tự mở Codex.

Có hai máy, mỗi máy lo một nền tảng:

| Máy | Nền tảng (nhãn issue) | Công cụ |
|---|---|---|
| **Windows** | `platform: web`, `platform: android` | Playwright, Maestro + `adb` (điện thoại Android thật) |
| **Mac** | `platform: ios` | Maestro + Xcode Simulator |

**Quy tắc: mỗi máy chỉ một phiên Codex tại một thời điểm.** Hai phiên cùng máy sẽ tranh nhau điện thoại/Simulator và ghi chồng kết quả.

## 1. Cấu hình GitHub MCP cho Codex (cả hai máy)

Tạo **fine-grained personal access token** của GitHub, chỉ chọn repo app cần test và cấp quyền **Issues: Read and write**. Repo riêng tư thì cấp thêm quyền đọc nội dung. Giữ token ngoài Git, truyền qua biến môi trường `GITHUB_PAT_TOKEN` trước khi mở Codex.

```bash
codex mcp add github --url https://api.githubcopilot.com/mcp/ --bearer-token-env-var GITHUB_PAT_TOKEN
codex mcp list
```

Hoặc thêm vào `~/.codex/config.toml`:

```toml
[mcp_servers.github]
url = "https://api.githubcopilot.com/mcp/"
bearer_token_env_var = "GITHUB_PAT_TOKEN"
```

Mở lại Codex, gõ `/mcp` để kiểm tra. Token này chỉ để **Codex đọc issue**; GitHub App của AI Test Runner mới là bên comment kết quả.

## 2. Biến môi trường (cả hai máy)

| Biến | Ý nghĩa |
|---|---|
| `AGENT_API_TOKEN` | Giống giá trị trong `.env` của AI Test Runner (chuỗi ngẫu nhiên dài). Để trống bên app thì API agent trả 404. |
| `AI_TEST_RUNNER_URL` | Địa chỉ app mà **máy chạy Codex** truy cập được, ví dụ `http://192.168.1.10:3000` (máy khác) hoặc `http://localhost:3000` (cùng máy). |
| `GITHUB_PAT_TOKEN` | Token GitHub cho Codex đọc issue (mục 1). |

Đặt chúng trong môi trường của tiến trình Codex, **không** ghi vào repo, prompt hay issue. Bên app, `APP_BASE_URL` trong `.env` cũng phải là địa chỉ mà máy Codex truy cập được, vì app ghi địa chỉ đó vào issue.

Ba biến `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` chỉ đặt ở `.env` của **app** (máy Codex không cần): Codex xin chữ ký từ app rồi đẩy file thẳng lên Cloudinary. Dự án lưu ở Google Drive thì script gửi file cho app và app đẩy lên Drive (Codex không cần thêm biến nào, `GOOGLE_OAUTH_*` cũng chỉ ở `.env` của app).

## 3. Cài đặt máy Windows (web + Android)

1. **Java 17 trở lên** (Maestro cần). Kiểm tra: `java -version`.
2. **Android platform-tools** để có `adb`. Kiểm tra: `adb version`.
3. **Điện thoại Android thật**: bật *Tuỳ chọn nhà phát triển* → bật **Gỡ lỗi USB**, cắm cáp, chấp nhận hộp thoại "Cho phép gỡ lỗi USB". Kiểm tra: `adb devices` phải thấy máy ở trạng thái `device` (không phải `unauthorized`).
4. **Maestro CLI**: cài theo hướng dẫn của Maestro, kiểm tra `maestro --version`.
5. **Maestro MCP trong Codex**: thêm server Maestro MCP vào Codex (`codex mcp add ...` hoặc `config.toml`), rồi `/mcp` để chắc nó hiện.
6. **Playwright** (cho web), trong thư mục bản sao repo app:
   ```bash
   npm install
   npx playwright install chromium
   ```
7. **Python + uv** để chạy script upload (bước 5 bên dưới), từ thư mục `backend/` của AI Test Runner: `uv sync`.

## 4. Cài đặt máy Mac (iOS)

1. **Xcode** (cài từ App Store) và mở một lần để chấp nhận giấy phép. Cài thêm **iOS Simulator runtime** trong Xcode → Settings → Platforms.
2. **Java 17 trở lên**, ví dụ `brew install openjdk@17`.
3. **Maestro CLI** và **Maestro MCP** trong Codex (như Windows).
4. Mở Simulator và cài file `.app` của app lên đó:
   ```bash
   xcrun simctl list devices        # chọn máy ảo, bật nó: xcrun simctl boot "<tên máy>"
   xcrun simctl install booted /đường/dẫn/MyApp.app
   ```
   Mã app iOS (bundle id) có sẵn trong issue ở dòng "Mã app iOS".
5. **Python + uv** và `uv sync` trong `backend/` để chạy script upload.

## 5. Bằng chứng: ảnh từng bước và video

Mỗi case cần **ảnh chụp sau mỗi bước** và **một video** cả lượt chạy. Mỗi file phải đẩy lên nơi lưu của dự án (Cloudinary hoặc Google Drive, script tự nhận) bằng script của app (từ thư mục `backend/`):

```bash
uv run python -m app.tools.upload_evidence --project PRJ-0001 --file buoc2.png --note "Bước 2"
```

Script in ra một dòng JSON `Media` (`kind`, `url`, `public_id`, `note`). Dán nguyên JSON đó vào `step_results[].screenshot` (ảnh từng bước), `evidence.video` hoặc `evidence.screenshots`. App từ chối link không thuộc đúng kho của nó (HTTP 422). Script báo lỗi tiếng Việt khi Drive chưa cấu hình (503), Drive lỗi (502) hoặc file quá lớn (413).

Cách quay video:

- **Web (Playwright):** bật `video: 'on'` trong cấu hình, lấy file `.webm` trong thư mục kết quả.
- **Android:** `adb shell screenrecord /sdcard/case.mp4`, dừng bằng Ctrl+C rồi `adb pull /sdcard/case.mp4`. **`screenrecord` chỉ quay tối đa 3 phút mỗi file**; case dài hơn thì quay nhiều đoạn, hoặc dùng `recordVideo` của Maestro.
- **iOS Simulator:** `xcrun simctl io booted recordVideo case.mp4`, dừng bằng Ctrl+C.
- **Maestro:** lệnh `startRecording` / `stopRecording` trong flow cũng cho ra video.

Chuỗi `evidence` kiểu cũ (một link `https://`) vẫn được nhận; đường dẫn file trên máy bị bỏ qua.

## 6. Prompt mẫu

Chỉ cần thay `<owner/repo>`. Mã dự án và endpoint đã có trong mục **Báo cáo cho AI Test Runner** của từng issue.

> **Bỏ qua issue test tay.** Issue có nhãn `mode: manual` là case do tester tự chạy bằng tay; **luôn bỏ qua**, không chạy và không gửi kết quả (API cũng từ chối với lý do "Case test tay"). Thêm điều kiện này vào mọi prompt bên dưới: *"Bỏ qua mọi issue có nhãn `mode: manual`."*

### Máy Windows (web và Android)

> Trong repo `<owner/repo>`, dùng GitHub MCP liệt kê issue **đang mở** có label `test-case`, `status:APPROVED` và **một trong hai** label `platform: web` hoặc `platform: android`. **Bỏ qua mọi issue `platform: ios`.** Với mỗi issue: đọc README/source của app, đọc "Điểm bắt đầu", "Mã app Android" và các ảnh hướng dẫn. Web thì viết kịch bản Playwright; Android thì chạy bằng Maestro trên điện thoại thật (`adb devices` phải thấy máy). Lấy PASS/FAIL từ **kết quả lệnh chạy và mã thoát**, không đoán. Không chạy được thì dùng `BLOCKED` hoặc `INCONCLUSIVE` kèm lý do.
>
> Bằng chứng: **chụp ảnh sau mỗi bước** và **quay một video cả lượt**, upload từng file bằng `uv run python -m app.tools.upload_evidence --project <mã dự án> --file <file> --note "<ghi chú>"` (chạy trong thư mục `backend/` của AI Test Runner), dùng JSON nó in ra. Android quay bằng `adb shell screenrecord` (tối đa 3 phút mỗi file).
>
> **Không tự comment lên issue.** Gọi đúng endpoint trong mục **Báo cáo cho AI Test Runner** bằng `Authorization: Bearer` từ biến `AGENT_API_TOKEN`, một phần tử mỗi case, gồm: `status`, `reason`, `failed_step`, `step_results` (mỗi bước có trạng thái và ảnh), `evidence.video`, `actual_result`, `environment` (ví dụ `Android 14 / Pixel 7` hoặc `Chrome 130 / Windows 11`), `executed_by` = `codex-windows`, và `case_version` lấy từ dòng **"Phiên bản case: vN"** trong issue (chỉ số N). Nếu comment "Yêu cầu chạy lại" của issue có dòng **Mã lần chạy**, gửi thêm `run_id` đó ở cấp ngoài cùng của request. Không đọc `.env`, không đưa token/mật khẩu vào issue hay comment. Cuối cùng báo lại mã run và các case bị API bỏ qua.

### Máy Mac (iOS)

> Trong repo `<owner/repo>`, dùng GitHub MCP liệt kê issue **đang mở** có label `test-case`, `status:APPROVED` và `platform: ios`. **Bỏ qua mọi issue có platform khác.** Với mỗi issue: đọc "Điểm bắt đầu", "Mã app iOS" và các ảnh hướng dẫn; chạy bằng Maestro trên **iOS Simulator** đang bật (app `.app` đã cài sẵn). Lấy PASS/FAIL từ kết quả lệnh và mã thoát. Không chạy được thì `BLOCKED`/`INCONCLUSIVE` kèm lý do.
>
> Bằng chứng: chụp ảnh sau mỗi bước, quay video bằng `xcrun simctl io booted recordVideo`, upload từng file bằng `uv run python -m app.tools.upload_evidence --project <mã dự án> --file <file> --note "<ghi chú>"` và dùng JSON nó in ra.
>
> **Không tự comment lên issue.** Gọi đúng endpoint trong mục **Báo cáo cho AI Test Runner** bằng `Authorization: Bearer` từ `AGENT_API_TOKEN`, một phần tử mỗi case, gồm `status`, `reason`, `failed_step`, `step_results`, `evidence.video`, `actual_result`, `environment` (ví dụ `iOS 17 / iPhone 15 Simulator`), `executed_by` = `codex-mac`, `case_version` lấy từ dòng **"Phiên bản case: vN"**, và `run_id` ở cấp ngoài cùng nếu comment chạy lại có **Mã lần chạy**. Không đọc `.env`. Báo lại mã run và các case bị API bỏ qua.

### Chạy lại (needs-rerun) và chạy bộ regression

QA Lead/Admin bấm **Chạy lại** (một case) hoặc **Chạy bộ regression** (nhiều case, nhập bản build) ở trang Kết quả. App chỉ để lại tín hiệu trên issue: comment "🔄 Yêu cầu chạy lại", mở lại issue và gắn nhãn `needs-rerun`. Khi chạy bộ regression, comment có thêm dòng `Mã lần chạy: RUN-xxxx`.

Dùng đúng prompt của máy mình ở trên, nhưng đổi điều kiện lọc thành issue **đang mở** có `needs-rerun`, và đọc comment lần trước để biết lỗi ở đâu. Với regression: gửi `run_id` = mã trong comment; có thể gửi nhiều đợt, run tự hoàn tất khi đủ case (hoặc QA Lead bấm **Kết thúc**). Case không thuộc run bị API bỏ qua.

## 7. Ví dụ gọi API

```bash
curl -X POST "$AI_TEST_RUNNER_URL/api/agent/projects/PRJ-0001/results" \
  -H "Authorization: Bearer $AGENT_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{
    "run_id": null,
    "results": [{
      "test_case_id": "TC-000002",
      "status": "FAIL",
      "reason": "Không thấy thông báo",
      "failed_step": 2,
      "case_version": 3,
      "environment": "Android 14 / Pixel 7",
      "executed_by": "codex-windows",
      "step_results": [
        {"step_no": 1, "status": "PASS"},
        {"step_no": 2, "status": "FAIL", "actual": "Không thấy thông báo", "screenshot": {"kind": "image", "url": "https://res.cloudinary.com/...", "public_id": "...", "note": "Bước 2"}}
      ],
      "evidence": {"video": {"kind": "video", "url": "https://res.cloudinary.com/...", "public_id": "...", "note": ""}, "screenshots": []}
    }]
  }'
```

Mỗi phần tử `step_results` có `step_no` (từ 1), `status` (`PASS`/`FAIL`/`SKIPPED`), `actual` (kết quả thực tế, tuỳ chọn) và `screenshot` (JSON `Media`, tuỳ chọn).

API trả `run_id`, số `written` và danh sách `ignored` (case không tồn tại/chưa duyệt, hoặc không thuộc lần chạy regression). Mỗi request nhận tối đa 200 kết quả. Lỗi thường gặp: 401 token sai; 404 `run_id` không tồn tại; 409 dự án đã lưu trữ, đang có lần ghi khác, hoặc `run_id` không phải run regression đang mở; 422 ảnh/video sai kho (Cloudinary/Drive); 503 Sheet lỗi (kiểm tra Sheet trước khi gửi lại). Không ghi `test_data` hoặc email người tạo/sửa vào issue của repo công khai.

Khi case FAIL, app tự giao issue cho **dev phụ trách** của màn hình (đặt ở trang Màn hình), gắn nhãn `bug: cần sửa`; chạy lại PASS thì bỏ nhãn bug. App chỉ giữ bằng chứng của 5 lần chạy gần nhất mỗi case.

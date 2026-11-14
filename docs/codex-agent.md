# Dùng Codex chạy test case từ GitHub issue

Luồng hiện tại: QA Lead duyệt case trên AI Test Runner → app tạo issue trong repo của dự án → bạn tự mở Codex để chạy test → Codex comment kết quả lên issue và gọi API để ghi vào tab `Results` của Google Sheet. App không tự mở Codex.

## 1. Cấu hình GitHub MCP cho Codex

Tạo **fine-grained personal access token** của GitHub, chỉ chọn repo app cần test và cấp quyền **Issues: Read and write**. Codex cần quyền đọc code của repo; nếu repo riêng tư, cấp thêm quyền đọc nội dung repo. Giữ token ngoài Git và truyền vào biến môi trường `GITHUB_PAT_TOKEN` trước khi mở Codex.

Theo [hướng dẫn Codex của GitHub MCP](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-codex.md) và [tài liệu MCP chính thức của OpenAI](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), thêm server bằng lệnh:

```bash
codex mcp add github --url https://api.githubcopilot.com/mcp/ --bearer-token-env-var GITHUB_PAT_TOKEN
codex mcp list
```

Hoặc thêm vào `~/.codex/config.toml` trên máy của bạn:

```toml
[mcp_servers.github]
url = "https://api.githubcopilot.com/mcp/"
bearer_token_env_var = "GITHUB_PAT_TOKEN"
```

Mở lại Codex, dùng `/mcp` để kiểm tra các công cụ GitHub đã hiện. Token này dành cho **Codex đọc/comment issue**; GitHub App trong AI Test Runner có cấu hình riêng.

## 2. Chuẩn bị nơi chạy test

- Mở Codex tại **bản sao repo app cần test trong một thư mục riêng**. Đọc README của app để biết cách khởi động và URL. Chỉ cho phép các lệnh cần thiết như `npm install`, `npm run dev`, `npx playwright install chromium`, `npx playwright test --reporter=json`.
- Cài Playwright và Chromium trong thư mục đó nếu app chưa có. Dùng tài khoản kiểm thử riêng khi cần đăng nhập. Không yêu cầu Codex mở `.env`, không chép mật khẩu hoặc token vào issue/comment.
- Trong `.env` **của AI Test Runner**, đặt `AGENT_API_TOKEN` là chuỗi ngẫu nhiên dài. Để trống thì API agent trả 404. Cung cấp token này cho tiến trình Codex qua biến môi trường, ngoài repo và ngoài prompt; không đưa giá trị token vào lời nhắn cho Codex.
- Nếu Codex chạy trên máy khác backend, thay `localhost:8000` trong ví dụ bên dưới bằng địa chỉ backend mà máy đó truy cập được.

## 3. Prompt mẫu cho Codex

Thay `<owner/repo>`, `<project_id>` và URL bằng giá trị của dự án:

> Trong repo `<owner/repo>`, dùng GitHub MCP liệt kê issue có cả hai label `test-case` và `status:APPROVED`. Đọc từng issue và README/source của app để hiểu cách chạy. Viết kịch bản Playwright cho các bước trong issue, chạy bằng `npx playwright test --reporter=json` và lưu báo cáo JSON. Lấy PASS/FAIL từ **báo cáo JSON và mã thoát của lệnh**, không tự đoán từ lời giải thích. Nếu không chạy được, dùng `BLOCKED` hoặc `INCONCLUSIVE` kèm lý do. Comment kết quả lên đúng issue: trạng thái, bước lỗi nếu có, và đường dẫn bằng chứng không chứa bí mật. Sau đó gọi `POST <backend_url>/api/agent/projects/<project_id>/results` bằng `Authorization: Bearer` lấy từ biến môi trường `AGENT_API_TOKEN`; gửi một phần tử kết quả cho mỗi case. Báo lại mã run và các case bị API bỏ qua. Không đọc `.env` và không đưa mật khẩu/token vào issue hay comment.

**Lưu ý:** API ghi Sheet không tự comment lên GitHub; Codex phải làm cả hai thao tác. Nếu issue đã cũ so với case trong Sheet, QA Lead bấm **Đồng bộ lại issue** trước khi chạy.

## 4. Ví dụ gọi API

Ví dụ cho terminal Bash, khi `AGENT_API_TOKEN` đã có trong môi trường của tiến trình Codex:

```bash
curl -X POST 'http://localhost:8000/api/agent/projects/PRJ-0001/results' \
  -H "Authorization: Bearer $AGENT_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"results":[{"test_case_id":"TC-000001","status":"PASS","reason":"Đạt"},{"test_case_id":"TC-000002","status":"FAIL","reason":"Không thấy thông báo","failed_step":2,"evidence":"artifacts/TC-000002.png"}]}'
```

API trả `run_id`, số `written` và danh sách `ignored` (case không tồn tại trong dự án hoặc chưa được duyệt). Mỗi request nhận tối đa 200 kết quả. Token sai trả 401; dự án đã lưu trữ hoặc đang có lần ghi khác trả 409. Nếu Sheet lỗi khi ghi kết quả, API trả 503 và đánh dấu run `FAILED`; hãy kiểm tra Sheet trước khi gửi lại. Không ghi `test_data` hoặc email người tạo/sửa vào issue của repo công khai.

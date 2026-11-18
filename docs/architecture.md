# Kiến trúc hệ thống AI Test Runner

## 1. Tổng quan — dữ liệu chạy ở đâu

```mermaid
flowchart TD
    subgraph Browser["Trình duyệt"]
        FE["Next.js Frontend\n(port 3000)"]
    end

    subgraph Backend["Backend (FastAPI)"]
        API["REST API\n/api/..."]
        AgentAPI["Agent API\n/api/agent/...\n(Bearer token)"]
    end

    subgraph Storage["Lưu trữ"]
        Sheet["Google Sheets\n── Users\n── Projects\n── Members\n── TestCases\n── Runs / Results\n── AuditLog"]
        Redis["Redis\nphiên đăng nhập\nthông báo mỗi user\n(tối đa 100, TTL 30 ngày)"]
    end

    subgraph External["Ngoài ứng dụng"]
        GHApp["GitHub App\ntạo / đồng bộ Issue"]
        Codex["Codex (AI Agent)\nchạy Playwright"]
        GHRepo["GitHub Repo\nIssues của dự án"]
        GHMCP["GitHub MCP\n(API Copilot)"]
    end

    FE -->|"REST / OpenAPI"| API
    API -->|"đọc-ghi tất cả dữ liệu"| Sheet
    API -->|"ghi thông báo"| Redis
    API -->|"đọc thông báo"| Redis
    API -->|"tạo / cập nhật Issue\nkhi case APPROVED"| GHApp
    GHApp -->|"GitHub API"| GHRepo

    FE -->|"đăng nhập: email + mật khẩu"| API
    API -->|"kiểm tra email + password_hash\ntrong tab Users"| Sheet
    API -->|"phiên đăng nhập\n+ đếm sai mật khẩu"| Redis

    Codex -->|"đọc Issue + label"| GHMCP
    GHMCP -->|"GitHub API"| GHRepo
    Codex -->|"comment kết quả lên Issue"| GHMCP
    Codex -->|"POST /api/agent/.../results\nAuthorization: Bearer AGENT_API_TOKEN"| AgentAPI
    AgentAPI -->|"ghi tab Runs / Results"| Sheet
```

> **Dữ liệu chính sống trong Google Sheets.** Redis chỉ giữ thông báo tạm thời — mất thông báo không mất dữ liệu. Codex chạy hoàn toàn ngoài app; nó liên lạc ngược lại qua một API riêng có token.

---

## 2. Luồng đăng nhập (email + mật khẩu)

```mermaid
sequenceDiagram
    actor User as Người dùng
    participant FE as Next.js
    participant BE as FastAPI
    participant Redis as Redis
    participant Sheet as Google Sheets

    User->>FE: Nhập email + mật khẩu
    FE->>BE: POST /api/auth/login
    BE->>Redis: đã sai quá 5 lần chưa?
    BE->>Sheet: get(email) + password_hash từ tab Users
    alt Email đúng, active = true, mật khẩu khớp hash (argon2)
        BE->>BE: tạo session cookie (lưu trong Redis)
        BE-->>FE: 200 + cookie
    else Sai email, sai mật khẩu hoặc active = false
        BE->>Redis: tăng đếm sai
        BE-->>FE: 401 (hoặc 429 nếu bị khoá 15 phút)
    end
```

> **Mật khẩu không lưu thẳng.** Tab Users chỉ giữ `password_hash` (argon2), cột này không bao giờ trả ra API. Admin tạo thành viên và đặt lại mật khẩu; người dùng tự đổi được. Mọi lần đổi hoặc đặt lại đều đăng xuất các phiên cũ.

---

## 3. Luồng Codex chạy test case

```mermaid
sequenceDiagram
    actor QA as QA Lead
    participant App as AI Test Runner
    participant Sheet as Google Sheets
    participant GH as GitHub Issues
    participant Codex as Codex (AI Agent)
    participant AgentAPI as Agent API

    QA->>App: Duyệt case (APPROVED)
    App->>GH: tạo Issue (label: test-case, status:APPROVED)
    App->>Sheet: lưu trạng thái case

    Note over Codex: QA Lead tự mở Codex thủ công

    Codex->>GH: liệt kê Issue có label test-case + APPROVED (qua MCP)
    GH-->>Codex: danh sách Issue + nội dung steps
    Codex->>Codex: viết kịch bản Playwright + chạy
    Codex->>GH: comment kết quả (PASS/FAIL/BLOCKED) lên Issue
    Codex->>AgentAPI: POST /api/agent/projects/{id}/results\n(Bearer AGENT_API_TOKEN)
    AgentAPI->>Sheet: ghi tab Runs + Results
    AgentAPI-->>Codex: { run_id, written, ignored }
    App->>App: gửi thông báo cho QA Lead (qua Redis)
```

> **Codex không tự khởi động.** QA Lead mở Codex và paste prompt mẫu từ `docs/codex-agent.md`. Codex đọc Issue qua GitHub MCP, chạy Playwright thật, rồi báo kết quả cả lên Issue lẫn vào API.

---

## Bản đồ thư mục nhanh

| Thư mục / file | Làm gì |
|---|---|
| `backend/app/api/routers/` | Các endpoint REST (auth, projects, test_cases, notifications, agent, results, …) |
| `backend/app/core/services/` | Logic nghiệp vụ (không biết HTTP) |
| `backend/app/core/repositories/` | Đọc-ghi Google Sheets |
| `backend/app/core/sheets/gateway.py` | Cổng duy nhất gọi Google API |
| `backend/app/core/notifications.py` | Lưu/đọc thông báo trong Redis |
| `backend/app/core/github/` | Tạo/đồng bộ GitHub Issue |
| `frontend/` | Next.js — giao diện người dùng |
| `docs/codex-agent.md` | Hướng dẫn cấu hình và dùng Codex |

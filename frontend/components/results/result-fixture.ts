import type { ResultItem } from "@/lib/api/types"

/** Dữ liệu mẫu cho test: một kết quả đầy đủ trường, test chỉ ghi đè phần cần. */
export function makeResult(changes: Partial<ResultItem> = {}): ResultItem {
  return {
    case_id: "TC-000005",
    case_title: "Đăng nhập thành công",
    screen_id: "SC-login",
    screen_name: "Đăng nhập",
    status: "FAIL",
    reason: "Sai mật khẩu vẫn đăng nhập được",
    failed_step: 2,
    evidence: { pruned: false },
    run_id: "RUN-0002",
    finished_at: "2026-11-14T10:00:00Z",
    platform: "ANDROID",
    regression: false,
    case_version: 2,
    environment: "Pixel 7 / Android 14",
    executed_by: "codex-windows",
    dev_owner: "nguyenvana",
    actual_result: "Màn hình báo lỗi",
    step_results: [],
    build_version: "1.4.2",
    issue_url: "https://github.com/org/web/issues?q=label%3Atc%3ATC-000005",
    ...changes,
  }
}

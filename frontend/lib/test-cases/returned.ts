import type { AuditEntry } from "@/lib/api/types"

/**
 * Lần "trả lại" cần hiện banner: chỉ khi lần ĐỔI TRẠNG THÁI mới nhất (dòng có diff.status)
 * chính là RETURN. Nếu sau đó case đã được gửi duyệt/duyệt/sửa về Nháp thì banner đã cũ.
 */
export function latestReturn(history: AuditEntry[]): AuditEntry | undefined {
  // sort ổn định: hai dòng cùng giây vẫn giữ thứ tự ghi
  const oldestFirst = [...history].sort((a, b) => a.at.localeCompare(b.at))
  const newestStatusChange = oldestFirst.reverse().find((entry) => "status" in entry.diff)
  return newestStatusChange?.action === "RETURN" ? newestStatusChange : undefined
}

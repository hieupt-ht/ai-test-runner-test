import type { ResultStatus, RunStatus } from "@/lib/api/types"

/** Thứ tự hiện thống kê: đạt, lỗi, bị chặn, chưa kết luận (màu theo spec mục 11). */
export const RESULT_STATUSES: ResultStatus[] = ["PASS", "FAIL", "BLOCKED", "INCONCLUSIVE"]

/** Run chưa xong: còn chờ worker nhận hoặc đang chạy. */
export function isRunActive(status: RunStatus): boolean {
  return status === "QUEUED" || status === "RUNNING"
}

export function countResults(results: { status: ResultStatus }[]): Record<ResultStatus, number> {
  const counts: Record<ResultStatus, number> = { PASS: 0, FAIL: 0, BLOCKED: 0, INCONCLUSIVE: 0 }
  for (const result of results) counts[result.status] += 1
  return counts
}

export function filterResults<T extends { status: ResultStatus }>(
  results: T[],
  status: ResultStatus | "ALL",
): T[] {
  return status === "ALL" ? results : results.filter((result) => result.status === status)
}

/** Đường dẫn ảnh chụp lỗi. `screenshot` lưu trong kết quả có dạng "RUN-0001/TC-000002.png". */
export function screenshotUrl(projectId: string, runId: string, screenshot: string): string {
  const filename = screenshot.split("/").pop() ?? screenshot
  return `/api/projects/${projectId}/runs/${runId}/screenshots/${filename}`
}

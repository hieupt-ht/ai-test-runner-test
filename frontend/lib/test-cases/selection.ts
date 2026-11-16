import type { BatchApproveResponse, TestCase } from "@/lib/api/types"

/** Mã các case đang Chờ duyệt (chỉ những case này mới duyệt hàng loạt được). */
export function approvableIds(cases: TestCase[]): string[] {
  return cases.filter((testCase) => testCase.status === "IN_REVIEW").map((testCase) => testCase.id)
}

/** Bấm một checkbox: thêm nếu chưa chọn, bỏ nếu đã chọn. Trả về tập mới, không sửa tập cũ. */
export function toggleId(selected: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(selected)
  if (!next.delete(id)) next.add(id)
  return next
}

/** Checkbox "chọn tất cả": chưa chọn đủ thì chọn hết, đã chọn đủ thì bỏ hết. */
export function toggleAll(selected: ReadonlySet<string>, ids: string[]): Set<string> {
  const allSelected = ids.length > 0 && ids.every((id) => selected.has(id))
  return allSelected ? new Set() : new Set(ids)
}

/** Dữ liệu gửi lên server: mỗi case đã chọn kèm version đang xem (server so với bản mới nhất). */
export function batchItems(selected: ReadonlySet<string>, cases: TestCase[]) {
  return cases
    .filter((testCase) => testCase.status === "IN_REVIEW" && selected.has(testCase.id))
    .map((testCase) => ({ case_id: testCase.id, version: testCase.version }))
}

/** Số case duyệt được / bị bỏ qua, để báo "duyệt được X, bỏ qua Y". */
export function batchSummary(result: Pick<BatchApproveResponse, "approved" | "skipped">) {
  return { approved: result.approved.length, skipped: result.skipped.length }
}

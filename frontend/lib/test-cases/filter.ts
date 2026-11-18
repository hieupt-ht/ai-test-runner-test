import type { ExecutionMode, Priority, Severity, TestCase, TestCaseStatus } from "@/lib/api/types"

export type CaseFilters = {
  screenId?: string
  status?: TestCaseStatus
  severity?: Severity
  priority?: Priority
  createdBy?: string
  executionMode?: ExecutionMode
  query: string
}

/** Chữ thường, bỏ dấu tiếng Việt, "đ" → "d", gộp khoảng trắng thừa. */
export function normalizeForSearch(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/gi, "d")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim()
}

/** Lọc ở trình duyệt. Chưa chọn trạng thái thì ẩn case DEPRECATED. */
export function filterTestCases(cases: TestCase[], filters: CaseFilters): TestCase[] {
  const query = normalizeForSearch(filters.query)
  return cases.filter((testCase) => {
    if (filters.status ? testCase.status !== filters.status : testCase.status === "DEPRECATED") {
      return false
    }
    if (filters.screenId && testCase.screen_id !== filters.screenId) return false
    if (filters.severity && testCase.severity !== filters.severity) return false
    if (filters.priority && testCase.priority !== filters.priority) return false
    if (filters.executionMode && testCase.execution_mode !== filters.executionMode) return false
    if (filters.createdBy && testCase.created_by !== filters.createdBy) return false
    if (query) {
      const haystack = normalizeForSearch(`${testCase.id} ${testCase.title}`)
      if (!haystack.includes(query)) return false
    }
    return true
  })
}

/** Cắt một trang (page bắt đầu từ 1). Danh sách trống vẫn có 1 trang. */
export function paginate<T>(
  items: T[],
  page: number,
  pageSize: number,
): { items: T[]; pageCount: number } {
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize))
  const start = (page - 1) * pageSize
  return { items: items.slice(start, start + pageSize), pageCount }
}

import { describe, expect, it } from "vitest"

import type { TestCase } from "@/lib/api/types"
import { filterTestCases, normalizeForSearch, paginate } from "@/lib/test-cases/filter"

function makeCase(overrides: Partial<TestCase>): TestCase {
  return {
    id: "TC-000001",
    screen_id: "SC-0001",
    title: "Một case",
    precondition: "",
    test_data: "",
    steps: [],
    expected_result: "",
    severity: "MEDIUM",
    priority: "P2",
    status: "DRAFT",
    created_by: "a@x.com",
    updated_by: "a@x.com",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    version: 1,
    platform: "WEB",
    test_type: "FUNCTIONAL",
    regression: false,
    start_point: "",
    guide_media: [],
    postcondition: "",
    requirement_ref: "",
    execution_mode: "MANUAL",
    ...overrides,
  }
}

describe("filterTestCases", () => {
  const login = makeCase({ id: "TC-000012", title: "Đăng nhập thành công" })
  const other = makeCase({ id: "TC-000013", title: "Đăng xuất" })

  it("tìm không dấu và không phân biệt hoa thường", () => {
    expect(filterTestCases([login, other], { query: "dang nhap" })).toEqual([login])
    expect(filterTestCases([login, other], { query: "  ĐĂNG   NHẬP " })).toEqual([login])
    expect(filterTestCases([login, other], { query: "tc-000012" })).toEqual([login])
    expect(normalizeForSearch("Đường  Đi ")).toBe("duong di")
  })

  it("mặc định ẩn case DEPRECATED, chọn trạng thái DEPRECATED thì hiện", () => {
    const old = makeCase({ id: "TC-000099", status: "DEPRECATED" })
    expect(filterTestCases([login, old], { query: "" })).toEqual([login])
    expect(filterTestCases([login, old], { query: "", status: "DEPRECATED" })).toEqual([old])
  })

  it("lọc kết hợp màn hình + severity + người tạo", () => {
    const match = makeCase({ id: "TC-000020", screen_id: "SC-0002", severity: "HIGH", created_by: "b@x.com" })
    const wrongScreen = makeCase({ id: "TC-000021", screen_id: "SC-0001", severity: "HIGH", created_by: "b@x.com" })
    const wrongSeverity = makeCase({ id: "TC-000022", screen_id: "SC-0002", severity: "LOW", created_by: "b@x.com" })
    const wrongUser = makeCase({ id: "TC-000023", screen_id: "SC-0002", severity: "HIGH", created_by: "c@x.com" })
    const result = filterTestCases([match, wrongScreen, wrongSeverity, wrongUser], {
      query: "",
      screenId: "SC-0002",
      severity: "HIGH",
      createdBy: "b@x.com",
    })
    expect(result).toEqual([match])
  })
})

describe("paginate", () => {
  it("chia trang và trả số trang", () => {
    const items = Array.from({ length: 51 }, (_, i) => i)
    expect(paginate(items, 1, 25).items).toHaveLength(25)
    const last = paginate(items, 3, 25)
    expect(last.pageCount).toBe(3)
    expect(last.items).toEqual([50])
    expect(paginate([], 1, 25).pageCount).toBe(1)
  })
})

describe("lọc theo cách chạy", () => {
  const cases = [
    makeCase({ id: "TC-000001", execution_mode: "MANUAL" }),
    makeCase({ id: "TC-000002", execution_mode: "AUTOMATION" }),
  ]

  it("chỉ lấy case đúng cách chạy", () => {
    const ids = (executionMode?: "MANUAL" | "AUTOMATION") =>
      filterTestCases(cases, { query: "", executionMode }).map((c) => c.id)
    expect(ids("MANUAL")).toEqual(["TC-000001"])
    expect(ids("AUTOMATION")).toEqual(["TC-000002"])
    expect(ids(undefined)).toEqual(["TC-000001", "TC-000002"])
  })
})

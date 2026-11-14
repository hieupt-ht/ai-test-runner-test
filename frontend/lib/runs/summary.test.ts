import { describe, expect, it } from "vitest"

import {
  RESULT_STATUSES,
  countResults,
  filterResults,
  isRunActive,
  screenshotUrl,
} from "@/lib/runs/summary"

const results = [
  { status: "PASS" as const },
  { status: "PASS" as const },
  { status: "FAIL" as const },
  { status: "BLOCKED" as const },
]

describe("isRunActive", () => {
  it("chỉ QUEUED và RUNNING là đang hoạt động", () => {
    expect(isRunActive("QUEUED")).toBe(true)
    expect(isRunActive("RUNNING")).toBe(true)
    expect(isRunActive("COMPLETED")).toBe(false)
    expect(isRunActive("FAILED")).toBe(false)
    expect(isRunActive("CANCELLED")).toBe(false)
  })
})

describe("countResults", () => {
  it("đếm đủ bốn trạng thái, trạng thái vắng mặt là 0", () => {
    expect(countResults(results)).toEqual({ PASS: 2, FAIL: 1, BLOCKED: 1, INCONCLUSIVE: 0 })
    expect(Object.keys(countResults([]))).toEqual(RESULT_STATUSES)
  })
})

describe("filterResults", () => {
  it("ALL giữ nguyên, một trạng thái thì lọc đúng", () => {
    expect(filterResults(results, "ALL")).toHaveLength(4)
    expect(filterResults(results, "PASS")).toHaveLength(2)
    expect(filterResults(results, "INCONCLUSIVE")).toEqual([])
  })
})

describe("screenshotUrl", () => {
  it("lấy tên file cuối của đường dẫn lưu trong kết quả", () => {
    expect(screenshotUrl("PRJ-0001", "RUN-0001", "RUN-0001/TC-000002.png")).toBe(
      "/api/projects/PRJ-0001/runs/RUN-0001/screenshots/TC-000002.png",
    )
  })
})

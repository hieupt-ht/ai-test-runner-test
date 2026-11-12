import { describe, expect, it } from "vitest"

import { deadlineState } from "@/lib/deadline"

const TODAY = "2026-11-12"

describe("deadlineState", () => {
  it("quá hạn khi deadline trước hôm nay", () => {
    expect(deadlineState("2026-11-10", TODAY)).toBe("overdue")
  })

  it("sắp tới hạn khi còn từ 0 đến 3 ngày", () => {
    expect(deadlineState("2026-11-12", TODAY)).toBe("due-soon")
    expect(deadlineState("2026-11-15", TODAY)).toBe("due-soon")
  })

  it("bình thường khi còn hơn 3 ngày", () => {
    expect(deadlineState("2026-11-16", TODAY)).toBe("ok")
  })

  it("tính đúng khi qua tháng", () => {
    expect(deadlineState("2026-12-01", "2026-11-29")).toBe("due-soon")
  })
})

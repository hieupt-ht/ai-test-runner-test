import { describe, expect, it } from "vitest"

import { insertStepAfter, moveStep, removeStep } from "@/lib/test-cases/steps"

const steps = [
  { action: "a", expected: "" },
  { action: "b", expected: "" },
  { action: "c", expected: "" },
]

describe("moveStep", () => {
  it("đổi chỗ đúng và không sửa mảng gốc", () => {
    const moved = moveStep(steps, 0, 2)
    expect(moved.map((s) => s.action)).toEqual(["b", "c", "a"])
    expect(steps.map((s) => s.action)).toEqual(["a", "b", "c"])
  })

  it("vị trí ngoài phạm vi thì giữ nguyên", () => {
    expect(moveStep(steps, 0, -1)).toEqual(steps)
    expect(moveStep(steps, 0, 3)).toEqual(steps)
  })
})

describe("insertStepAfter", () => {
  it("chèn bước trống ngay sau vị trí", () => {
    const result = insertStepAfter(steps, 0)
    expect(result.map((s) => s.action)).toEqual(["a", "", "b", "c"])
    expect(result[1]).toEqual({ action: "", expected: "" })
  })
})

describe("removeStep", () => {
  it("xoá đúng bước", () => {
    expect(removeStep(steps, 1).map((s) => s.action)).toEqual(["a", "c"])
  })

  it("không xoá bước cuối cùng", () => {
    const only = [{ action: "a", expected: "" }]
    expect(removeStep(only, 0)).toEqual(only)
  })
})

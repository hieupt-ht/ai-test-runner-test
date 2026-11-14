import { describe, expect, it } from "vitest"

import {
  AUTO_TYPES,
  autoHasValueField,
  autoNeedsTarget,
  autoNeedsValue,
  defaultAuto,
  insertStepAfter,
  isAutoComplete,
  moveStep,
  removeStep,
} from "@/lib/test-cases/steps"

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

describe("bước tự động", () => {
  it("AUTO_TYPES đúng thứ tự cố định", () => {
    expect(AUTO_TYPES).toEqual([
      "goto",
      "fill",
      "click",
      "select",
      "see_text",
      "not_see_text",
      "url_is",
    ])
  })

  it("autoNeedsTarget: chỉ nhập chữ, bấm và chọn cần chỉ ra phần tử", () => {
    expect(AUTO_TYPES.filter(autoNeedsTarget)).toEqual(["fill", "click", "select"])
  })

  it("autoNeedsValue: bấm và nhập chữ được để trống giá trị, các loại khác bắt buộc", () => {
    expect(AUTO_TYPES.filter(autoNeedsValue)).toEqual([
      "goto",
      "select",
      "see_text",
      "not_see_text",
      "url_is",
    ])
  })

  it("autoHasValueField: mọi loại trừ bấm có ô giá trị", () => {
    expect(AUTO_TYPES.filter(autoHasValueField)).toEqual([
      "goto",
      "fill",
      "select",
      "see_text",
      "not_see_text",
      "url_is",
    ])
  })

  it("defaultAuto: có phần tử đúng loại khi cần, không có khi không cần", () => {
    expect(defaultAuto("goto")).toEqual({ type: "goto", value: "" })
    expect(defaultAuto("fill")).toEqual({
      type: "fill",
      value: "",
      target: { by: "label", value: "" },
    })
    expect(defaultAuto("select").target?.by).toBe("label")
    expect(defaultAuto("click").target).toEqual({ by: "text", value: "" })
  })

  it("isAutoComplete: kiểm tra phần tử và giá trị bắt buộc", () => {
    expect(isAutoComplete(defaultAuto("click"))).toBe(false)
    expect(isAutoComplete({ type: "click", target: { by: "text", value: "Gửi" }, value: "" })).toBe(
      true,
    )
    expect(isAutoComplete(defaultAuto("goto"))).toBe(false)
    expect(isAutoComplete({ type: "goto", value: "/login" })).toBe(true)
    expect(
      isAutoComplete({ type: "fill", target: { by: "label", value: "Email" }, value: "" }),
    ).toBe(true)
  })

  it("insertStepAfter vẫn tạo bước trống không có auto", () => {
    expect(insertStepAfter(steps, 0)[1]).not.toHaveProperty("auto")
  })
})

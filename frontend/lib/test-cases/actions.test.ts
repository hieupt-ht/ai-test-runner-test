import { describe, expect, it } from "vitest"

import { availableActions } from "@/lib/test-cases/actions"

describe("availableActions", () => {
  it("theo trạng thái và quyền", () => {
    expect(availableActions("DRAFT", true, false, "AUTOMATION")).toEqual(["submit", "deprecate"])
    expect(availableActions("IN_REVIEW", true, true, "AUTOMATION")).toEqual(["approve", "return", "deprecate"])
    expect(availableActions("IN_REVIEW", true, false, "AUTOMATION")).toEqual(["deprecate"])
    expect(availableActions("DEPRECATED", true, false, "AUTOMATION")).toEqual([])
    expect(availableActions("DEPRECATED", true, true, "AUTOMATION")).toEqual(["restore"])
    expect(availableActions("APPROVED", false, true, "AUTOMATION")).toEqual([])
  })

  it("case Manual Nháp không có submit", () => {
    expect(availableActions("DRAFT", true, true, "MANUAL")).toEqual(["deprecate"])
  })

  it("case Manual đã kiểm thử vẫn cho ngừng dùng", () => {
    expect(availableActions("TESTED", true, false, "MANUAL")).toEqual(["deprecate"])
  })
})

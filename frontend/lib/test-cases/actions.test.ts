import { describe, expect, it } from "vitest"

import { availableActions } from "@/lib/test-cases/actions"

describe("availableActions", () => {
  it("theo trạng thái và quyền", () => {
    expect(availableActions("DRAFT", true, false)).toEqual(["submit", "deprecate"])
    expect(availableActions("IN_REVIEW", true, true)).toEqual(["approve", "return", "deprecate"])
    expect(availableActions("IN_REVIEW", true, false)).toEqual(["deprecate"])
    expect(availableActions("DEPRECATED", true, false)).toEqual([])
    expect(availableActions("DEPRECATED", true, true)).toEqual(["restore"])
    expect(availableActions("APPROVED", false, true)).toEqual([])
  })
})

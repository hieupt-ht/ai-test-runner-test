import { describe, expect, it } from "vitest"

import type { Media } from "@/lib/api/types"
import {
  isValidAssignee,
  limitEvidence,
  normalizeAssignee,
  splitEvidence,
} from "@/lib/test-cases/manual-run"

const image = (id: string): Media => ({ kind: "image", url: `u/${id}`, public_id: id, note: "" })
const video = (id: string): Media => ({ kind: "video", url: `u/${id}`, public_id: id, note: "" })

describe("tên GitHub người được giao", () => {
  it("bỏ @ và khoảng trắng ở đầu/cuối", () => {
    expect(normalizeAssignee("  @nguyenvana ")).toBe("nguyenvana")
  })

  it.each(["", "nguyenvana", "tran-b", "A1-b2"])("%j hợp lệ", (value) => {
    expect(isValidAssignee(value)).toBe(true)
  })

  it.each(["-abc", "abc-", "a--b", "có dấu", "a b", "x".repeat(40)])("%j không hợp lệ", (value) => {
    expect(isValidAssignee(value)).toBe(false)
  })
})

describe("bằng chứng", () => {
  it("tách một video và các ảnh", () => {
    expect(splitEvidence([image("a"), video("v"), image("b")])).toEqual({
      video: video("v"),
      screenshots: [image("a"), image("b")],
    })
  })

  it("không có video thì video là null", () => {
    expect(splitEvidence([image("a")])).toEqual({ video: null, screenshots: [image("a")] })
  })

  it("chỉ giữ một video (cái đầu) và tối đa 20 ảnh", () => {
    const many = Array.from({ length: 22 }, (_, i) => image(`i${i}`))
    const limited = limitEvidence([video("v1"), video("v2"), ...many])
    expect(limited.filter((m) => m.kind === "video")).toEqual([video("v1")])
    expect(limited.filter((m) => m.kind === "image")).toHaveLength(20)
  })
})

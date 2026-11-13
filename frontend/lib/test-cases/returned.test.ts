import { describe, expect, it } from "vitest"

import type { AuditEntry } from "@/lib/api/types"
import { latestReturn } from "@/lib/test-cases/returned"

function entry(at: string, action: string, diff: Record<string, unknown> = {}): AuditEntry {
  return { at: `2026-01-01T${at}Z`, actor: "x@x.com", action, diff }
}

const create = entry("08:00:00", "CREATE")
const submit = entry("09:00:00", "SUBMIT", { status: ["DRAFT", "IN_REVIEW"] })
const back = entry("10:00:00", "RETURN", { status: ["IN_REVIEW", "DRAFT"], comment: "Sai" })
const approve = entry("11:00:00", "APPROVE", { status: ["IN_REVIEW", "APPROVED"] })
const editToDraft = entry("12:00:00", "UPDATE", { status: ["APPROVED", "DRAFT"], title: ["a", "b"] })

describe("latestReturn", () => {
  it("có banner khi lần đổi trạng thái mới nhất là RETURN", () => {
    expect(latestReturn([create, submit, back])).toBe(back)
  })

  it("sửa nội dung không đổi trạng thái thì vẫn còn banner", () => {
    const plainEdit = entry("11:00:00", "UPDATE", { title: ["a", "b"] })
    expect(latestReturn([create, submit, back, plainEdit])).toBe(back)
  })

  it("trả lại -> gửi duyệt -> duyệt -> sửa về Nháp thì không còn banner", () => {
    const resubmit = entry("10:30:00", "SUBMIT", { status: ["DRAFT", "IN_REVIEW"] })
    expect(latestReturn([create, submit, back, resubmit, approve, editToDraft])).toBeUndefined()
  })

  it("không phụ thuộc thứ tự mảng và chưa từng trả lại thì không có banner", () => {
    expect(latestReturn([back, create, submit])).toBe(back)
    expect(latestReturn([create, submit])).toBeUndefined()
    expect(latestReturn([])).toBeUndefined()
  })
})

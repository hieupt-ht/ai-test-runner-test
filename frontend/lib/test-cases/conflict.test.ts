import { describe, expect, it } from "vitest"

import { ApiError } from "@/lib/api/client"
import type { TestCase } from "@/lib/api/types"
import { conflictFrom } from "@/lib/test-cases/conflict"

const latest = { id: "TC-000001", version: 3 } as TestCase

describe("conflictFrom", () => {
  it("lấy latest từ ApiError 409", () => {
    const body = { detail: "Case này vừa được An cập nhật. Vui lòng tải lại.", latest }
    const error = new ApiError(409, body.detail, body)
    expect(conflictFrom(error)).toEqual({ message: body.detail, latest })
  })

  it("trả null với 409 không có latest và với lỗi khác", () => {
    expect(conflictFrom(new ApiError(409, "Không hợp lệ", { detail: "Không hợp lệ" }))).toBeNull()
    expect(conflictFrom(new ApiError(409, "Bận"))).toBeNull()
    expect(conflictFrom(new ApiError(422, "x", { detail: "x", latest }))).toBeNull()
    expect(conflictFrom(new Error("x"))).toBeNull()
    expect(conflictFrom(null)).toBeNull()
  })
})

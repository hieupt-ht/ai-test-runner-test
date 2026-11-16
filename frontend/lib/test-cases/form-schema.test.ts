import { describe, expect, it } from "vitest"

import { testCaseFormSchema } from "@/lib/test-cases/form-schema"

const valid = {
  title: "Đăng nhập đúng",
  precondition: "",
  test_data: "",
  steps: [{ action: "Mở trang", expected: "" }],
  expected_result: "Vào được trang chủ",
  severity: "MEDIUM",
  priority: "P2",
}

describe("testCaseFormSchema", () => {
  it("chấp nhận dữ liệu hợp lệ", () => {
    expect(testCaseFormSchema.safeParse(valid).success).toBe(true)
  })

  it("báo lỗi khi không có bước", () => {
    expect(testCaseFormSchema.safeParse({ ...valid, steps: [] }).success).toBe(false)
  })

  it("báo lỗi khi action của bước rỗng (kể cả toàn khoảng trắng)", () => {
    const steps = [{ action: "   ", expected: "" }]
    expect(testCaseFormSchema.safeParse({ ...valid, steps }).success).toBe(false)
  })

  it("báo lỗi khi tiêu đề quá 200 ký tự", () => {
    expect(testCaseFormSchema.safeParse({ ...valid, title: "x".repeat(201) }).success).toBe(false)
    expect(testCaseFormSchema.safeParse({ ...valid, title: "x".repeat(200) }).success).toBe(true)
  })

  it("báo lỗi khi quá 50 bước hoặc thiếu kết quả mong đợi", () => {
    const steps = Array.from({ length: 51 }, () => ({ action: "a", expected: "" }))
    expect(testCaseFormSchema.safeParse({ ...valid, steps }).success).toBe(false)
    expect(testCaseFormSchema.safeParse({ ...valid, expected_result: " " }).success).toBe(false)
  })
})

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

  describe("bước tự động", () => {
    const withAuto = (auto: unknown) => ({
      ...valid,
      steps: [{ action: "Mở trang", expected: "", auto }],
    })

    it("case cũ không có auto vẫn hợp lệ", () => {
      expect(testCaseFormSchema.safeParse(valid).success).toBe(true)
    })

    it("chấp nhận auto: null, đúng như API trả về cho bước chưa có phần tự động", () => {
      const result = testCaseFormSchema.safeParse(withAuto(null))
      expect(result.success).toBe(true)
    })

    it("chấp nhận auto hợp lệ và giữ nguyên khi parse", () => {
      const auto = { type: "fill", target: { by: "label", value: "Email" }, value: "qa@x.com" }
      const result = testCaseFormSchema.safeParse(withAuto(auto))
      expect(result.success).toBe(true)
      expect(result.data?.steps[0].auto).toEqual(auto)
    })

    it("báo lỗi autoTargetRequired khi loại cần phần tử mà thiếu", () => {
      const result = testCaseFormSchema.safeParse(withAuto({ type: "click", value: "" }))
      expect(result.success).toBe(false)
      expect(result.error?.issues.map((i) => i.message)).toContain("autoTargetRequired")
    })

    it("báo lỗi khi phần tử có nhưng chữ/nhãn để trống", () => {
      const auto = { type: "click", target: { by: "text", value: "  " }, value: "" }
      const result = testCaseFormSchema.safeParse(withAuto(auto))
      expect(result.success).toBe(false)
      expect(result.error?.issues.map((i) => i.message)).toContain("autoTargetRequired")
    })

    it("báo lỗi autoValueRequired khi loại bắt buộc giá trị mà để trống", () => {
      const result = testCaseFormSchema.safeParse(withAuto({ type: "goto", value: " " }))
      expect(result.success).toBe(false)
      expect(result.error?.issues.map((i) => i.message)).toContain("autoValueRequired")
    })

    it("nhập chữ được để trống giá trị (để xoá ô)", () => {
      const auto = { type: "fill", target: { by: "label", value: "Email" }, value: "" }
      expect(testCaseFormSchema.safeParse(withAuto(auto)).success).toBe(true)
    })

    it("báo lỗi autoValueTooLong khi giá trị quá 500 ký tự", () => {
      const auto = { type: "goto", value: "x".repeat(501) }
      const result = testCaseFormSchema.safeParse(withAuto(auto))
      expect(result.error?.issues.map((i) => i.message)).toContain("autoValueTooLong")
    })
  })
})

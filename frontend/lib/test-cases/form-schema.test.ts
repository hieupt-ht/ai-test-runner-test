import { describe, expect, it } from "vitest"

import { testCaseFormSchema } from "@/lib/test-cases/form-schema"

const valid = {
  title: "Đăng nhập đúng",
  precondition: "",
  test_data: "",
  steps: [{ action: "Mở trang", expected: "", guide_media: [] }],
  expected_result: "Vào được trang chủ",
  severity: "MEDIUM",
  priority: "P2",
  platform: "WEB",
  test_type: "FUNCTIONAL",
  regression: false,
  start_point: "",
  guide_media: [],
  postcondition: "",
  requirement_ref: "",
}

describe("testCaseFormSchema", () => {
  it("chấp nhận dữ liệu hợp lệ", () => {
    expect(testCaseFormSchema.safeParse(valid).success).toBe(true)
  })

  it("báo lỗi khi không có bước", () => {
    expect(testCaseFormSchema.safeParse({ ...valid, steps: [] }).success).toBe(false)
  })

  it("báo lỗi khi action của bước rỗng (kể cả toàn khoảng trắng)", () => {
    const steps = [{ action: "   ", expected: "", guide_media: [] }]
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

  it("nhận ảnh/video hướng dẫn nhưng không quá 5 mục mỗi nơi", () => {
    const media = { kind: "image", url: "https://res.cloudinary.com/c/a.png", public_id: "a", note: "" }
    expect(testCaseFormSchema.safeParse({ ...valid, guide_media: [media] }).success).toBe(true)
    expect(
      testCaseFormSchema.safeParse({ ...valid, guide_media: Array(6).fill(media) }).success,
    ).toBe(false)
    const steps = [{ action: "a", expected: "", guide_media: Array(6).fill(media) }]
    expect(testCaseFormSchema.safeParse({ ...valid, steps }).success).toBe(false)
  })

  it("từ chối nền tảng hoặc loại test lạ", () => {
    expect(testCaseFormSchema.safeParse({ ...valid, platform: "WINDOWS" }).success).toBe(false)
    expect(testCaseFormSchema.safeParse({ ...valid, test_type: "OTHER" }).success).toBe(false)
  })
})

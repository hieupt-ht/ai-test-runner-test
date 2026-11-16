import { describe, expect, it } from "vitest"

import { userFormSchema } from "@/components/users/user-form-schema"

describe("userFormSchema", () => {
  it("chấp nhận dữ liệu hợp lệ và chuẩn hoá email", () => {
    const result = userFormSchema.safeParse({ email: "  An@X.com ", name: "An", role: "TESTER" })
    expect(result.success).toBe(true)
    expect(result.data?.email).toBe("an@x.com")
  })

  it("báo lỗi email sai định dạng bằng tiếng Việt", () => {
    const result = userFormSchema.safeParse({ email: "abc", name: "An", role: "TESTER" })
    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe("Email không hợp lệ")
  })

  it("báo lỗi khi tên trống", () => {
    const result = userFormSchema.safeParse({ email: "an@x.com", name: "  ", role: "TESTER" })
    expect(result.success).toBe(false)
    expect(result.error?.issues[0]?.message).toBe("Vui lòng nhập tên")
  })
})

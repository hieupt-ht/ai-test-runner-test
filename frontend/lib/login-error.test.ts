import { describe, expect, it } from "vitest"

import { loginErrorKey } from "@/lib/login-error"

describe("loginErrorKey", () => {
  it("đổi mã lỗi trên URL thành key thông báo", () => {
    expect(loginErrorKey("not_allowed")).toBe("login.notAllowed")
    expect(loginErrorKey("oauth_failed")).toBe("login.oauthFailed")
  })

  it("không có lỗi hoặc mã lạ thì không hiện gì", () => {
    expect(loginErrorKey(null)).toBeNull()
    expect(loginErrorKey("abc")).toBeNull()
  })
})

import { describe, expect, it } from "vitest"

import type { Assignment, Screen, User } from "@/lib/api/types"
import { selectableScreens } from "@/lib/test-cases/selectable-screens"

const screens = [
  { id: "SC-0001", name: "Đăng nhập" },
  { id: "SC-0002", name: "Đăng ký" },
] as Screen[]
const assignments = [{ screen_id: "SC-0002", assignee_email: "an@x.com" }] as Assignment[]

function user(role: User["role"], email: string): User {
  return { email, role } as User
}

describe("selectableScreens", () => {
  it("tester chỉ thấy màn hình được giao cho mình", () => {
    expect(selectableScreens(screens, assignments, user("TESTER", "an@x.com"))).toEqual([screens[1]])
  })

  it("tester chưa được giao gì thì không có màn hình nào", () => {
    expect(selectableScreens(screens, assignments, user("TESTER", "binh@x.com"))).toEqual([])
  })

  it("vai trò khác thấy mọi màn hình", () => {
    expect(selectableScreens(screens, assignments, user("QA_LEAD", "lead@x.com"))).toEqual(screens)
  })

  it("chưa biết người dùng thì không đưa ra màn hình nào", () => {
    expect(selectableScreens(screens, assignments, null)).toEqual([])
  })
})

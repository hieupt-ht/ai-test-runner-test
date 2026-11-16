import { describe, expect, it } from "vitest"

import vi from "@/messages/vi.json"
import { NAV_ITEMS, visibleNavItems } from "@/lib/nav"

function hrefs(role: Parameters<typeof visibleNavItems>[0]) {
  return visibleNavItems(role).map((item) => item.href)
}

describe("visibleNavItems", () => {
  it("chỉ ADMIN thấy mục Người dùng", () => {
    expect(hrefs("ADMIN")).toContain("/admin/users")
    expect(hrefs("QA_LEAD")).not.toContain("/admin/users")
    expect(hrefs("TESTER")).not.toContain("/admin/users")
    expect(hrefs("VIEWER")).not.toContain("/admin/users")
  })

  it("ai cũng thấy Tổng quan", () => {
    expect(hrefs("VIEWER")).toContain("/")
  })
})

describe("vi.json", () => {
  it("mọi key dùng trong NAV_ITEMS đều có bản dịch", () => {
    const nav = vi.nav as Record<string, string>
    for (const item of NAV_ITEMS) {
      expect(nav[item.labelKey], item.labelKey).toBeTruthy()
    }
  })
})

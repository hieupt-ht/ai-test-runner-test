import { describe, expect, it } from "vitest"

import { PROJECT_TABS, visibleProjectTabs } from "@/lib/project-tabs"
import vi from "@/messages/vi.json"

describe("visibleProjectTabs", () => {
  it("tab Cài đặt chỉ hiện khi có quyền MANAGE_PROJECTS", () => {
    const lead = visibleProjectTabs(["VIEW_PROJECT", "MANAGE_SCREENS"]).map((tab) => tab.segment)
    const admin = visibleProjectTabs(["VIEW_PROJECT", "MANAGE_PROJECTS"]).map((tab) => tab.segment)

    expect(lead).toEqual(["screens", "assignments", "members"])
    expect(admin).toContain("settings")
  })

  it("mọi labelKey của PROJECT_TABS đều có trong vi.json", () => {
    const labels = vi.projectTabs as Record<string, string>
    for (const tab of PROJECT_TABS) {
      expect(labels[tab.labelKey], tab.labelKey).toBeTruthy()
    }
  })
})

import { describe, expect, it } from "vitest"

import { PROJECT_TABS, visibleProjectTabs } from "@/lib/project-tabs"
import vi from "@/messages/vi.json"

describe("visibleProjectTabs", () => {
  it("tab Cài đặt hiện khi có quyền MANAGE_PROJECT_SETTINGS (Admin và QA Lead)", () => {
    const tester = visibleProjectTabs(["VIEW_PROJECT", "MANAGE_SCREENS"]).map((tab) => tab.segment)
    const lead = visibleProjectTabs(["VIEW_PROJECT", "MANAGE_PROJECT_SETTINGS"]).map(
      (tab) => tab.segment,
    )

    expect(tester).toEqual(["screens", "test-cases", "results", "assignments", "members"])
    expect(lead).toContain("settings")
  })

  it("tab Test case nằm ngay sau Màn hình và có nhãn trong vi.json", () => {
    const segments = PROJECT_TABS.map((tab) => tab.segment)
    expect(segments.indexOf("test-cases")).toBe(segments.indexOf("screens") + 1)
    expect((vi.projectTabs as Record<string, string>)["testCases"]).toBeTruthy()
  })

  it("mọi labelKey của PROJECT_TABS đều có trong vi.json", () => {
    const labels = vi.projectTabs as Record<string, string>
    for (const tab of PROJECT_TABS) {
      expect(labels[tab.labelKey], tab.labelKey).toBeTruthy()
    }
  })
})

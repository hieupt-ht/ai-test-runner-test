import type { Action } from "@/lib/api/types"

export type ProjectTab = {
  /** Phần cuối đường dẫn: /projects/<id>/<segment> */
  segment: string
  /** Key trong messages/vi.json, nhóm "projectTabs" */
  labelKey: string
  /** Quyền cần có để thấy tab */
  permission: Action
}

export const PROJECT_TABS: ProjectTab[] = [
  { segment: "overview", labelKey: "overview", permission: "VIEW_PROJECT" },
  { segment: "screens", labelKey: "screens", permission: "VIEW_PROJECT" },
  { segment: "test-cases", labelKey: "testCases", permission: "VIEW_PROJECT" },
  { segment: "results", labelKey: "results", permission: "VIEW_PROJECT" },
  { segment: "assignments", labelKey: "assignments", permission: "VIEW_PROJECT" },
  { segment: "members", labelKey: "members", permission: "VIEW_PROJECT" },
  { segment: "settings", labelKey: "settings", permission: "MANAGE_PROJECT_SETTINGS" },
]

export function visibleProjectTabs(permissions: Action[]): ProjectTab[] {
  return PROJECT_TABS.filter((tab) => permissions.includes(tab.permission))
}

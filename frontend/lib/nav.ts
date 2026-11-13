import { FolderCog, LayoutDashboard, ListChecks, Users, type LucideIcon } from "lucide-react"

import type { Role } from "@/lib/api/types"

export type NavItem = {
  href: string
  /** Key trong messages/vi.json, nhóm "nav" */
  labelKey: string
  icon: LucideIcon
  /** Những vai trò được thấy mục này trên menu */
  roles: Role[]
}

export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    labelKey: "overview",
    icon: LayoutDashboard,
    roles: ["ADMIN", "QA_LEAD", "TESTER", "VIEWER"],
  },
  {
    href: "/my-work",
    labelKey: "myWork",
    icon: ListChecks,
    roles: ["ADMIN", "QA_LEAD", "TESTER", "VIEWER"],
  },
  { href: "/admin/projects", labelKey: "adminProjects", icon: FolderCog, roles: ["ADMIN"] },
  { href: "/admin/users", labelKey: "users", icon: Users, roles: ["ADMIN"] },
]

export function visibleNavItems(role: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role))
}

"use client"

import { FlaskConical, FolderKanban } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"

import type { Role } from "@/lib/api/types"
import { visibleNavItems } from "@/lib/nav"
import { cn } from "@/lib/utils"

export function Sidebar({ role }: { role: Role }) {
  const t = useTranslations()
  const pathname = usePathname()

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground md:flex">
      <div className="flex h-14 items-center gap-2 border-b px-4 font-semibold">
        <FlaskConical className="size-5 text-primary" />
        {t("app.name")}
      </div>

      <nav className="flex flex-col gap-1 p-2">
        {visibleNavItems(role).map((item) => {
          const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
              )}
            >
              <item.icon className="size-4" />
              {t(`nav.${item.labelKey}`)}
            </Link>
          )
        })}
      </nav>

      <div className="mt-2 px-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {t("nav.projects")}
      </div>
      <div className="m-2 flex items-center gap-2 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
        <FolderKanban className="size-4" />
        {t("nav.projectsComingSoon")}
      </div>
    </aside>
  )
}

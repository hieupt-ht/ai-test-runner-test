"use client"

import { Archive, ChevronDown, ChevronRight, FlaskConical, FolderKanban } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"
import { useTranslations } from "next-intl"

import type { Role } from "@/lib/api/types"
import { visibleNavItems } from "@/lib/nav"
import { visibleProjectTabs } from "@/lib/project-tabs"
import { useProject, useProjects } from "@/lib/use-projects"
import { cn } from "@/lib/utils"

export function Sidebar({ role }: { role: Role }) {
  const t = useTranslations()
  const pathname = usePathname()
  const { data: projects = [] } = useProjects()
  const [expanded, setExpanded] = useState<string[]>([])

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`)
  const nav = (
    <>
      <div className="flex h-14 items-center gap-2 border-b px-4 font-semibold">
        <FlaskConical className="size-5 text-primary" />
        {t("app.name")}
      </div>
      <nav className="flex flex-col gap-1 p-2">
        {visibleNavItems(role).map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive(item.href) ? "page" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
              isActive(item.href)
                ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
            )}
          >
            <item.icon className="size-4" />
            {t(`nav.${item.labelKey}`)}
          </Link>
        ))}
      </nav>
      <div className="mt-2 px-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {t("nav.projects")}
      </div>
      <nav className="flex flex-col gap-1 overflow-y-auto p-2">
        {projects.length === 0 && (
          <p className="px-3 py-2 text-xs text-muted-foreground">{t("nav.noProjects")}</p>
        )}
        {projects.map((project) => (
          <ProjectTreeItem
            key={project.id}
            project={project}
            pathname={pathname}
            isExpanded={expanded.includes(project.id)}
            onToggle={() => setExpanded((items) =>
              items.includes(project.id)
                ? items.filter((id) => id !== project.id)
                : [...items, project.id],
            )}
          />
        ))}
      </nav>
    </>
  )

  return (
    <>
      <aside className="hidden w-60 shrink-0 flex-col overflow-y-auto border-r bg-sidebar text-sidebar-foreground md:flex">
        {nav}
      </aside>
      <div className="border-b bg-sidebar md:hidden">
        <details>
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium">{t("nav.menu")}</summary>
          <div className="max-h-[70vh] overflow-y-auto pb-2">{nav}</div>
        </details>
      </div>
    </>
  )
}

function ProjectTreeItem({
  project,
  pathname,
  isExpanded,
  onToggle,
}: {
  project: { id: string; name: string; archived: boolean }
  pathname: string
  isExpanded: boolean
  onToggle: () => void
}) {
  const t = useTranslations()
  const root = `/projects/${project.id}`
  const isProjectActive = pathname === root || pathname.startsWith(`${root}/`)
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`)
  const { data } = useProject(project.id)
  const tabs = visibleProjectTabs(data?.permissions ?? [])

  return (
    <div>
              <button
                type="button"
                aria-expanded={isProjectActive || isExpanded}
                aria-label={project.name}
                onClick={onToggle}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent/60 hover:text-foreground"
              >
                {isExpanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                {project.archived ? <Archive className="size-4" /> : <FolderKanban className="size-4" />}
                <span className="truncate">{project.name}</span>
              </button>
              {(isProjectActive || isExpanded) && (
                <div className="ml-5 flex flex-col gap-1 border-l pl-2">
                  <Link
                    href={root}
                    aria-current={pathname === root ? "page" : undefined}
                    className={cn(
                      "rounded-md px-3 py-2 text-sm transition-colors",
                      pathname === root
                        ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                        : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                    )}
                  >
                    {t("nav.overview")}
                  </Link>
                  {tabs.map((tab) => {
                    const href = `${root}/${tab.segment}`
                    return (
                      <Link
                        key={tab.segment}
                        href={href}
                        aria-current={isActive(href) ? "page" : undefined}
                        className={cn(
                          "rounded-md px-3 py-2 text-sm transition-colors",
                          isActive(href)
                            ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                            : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                        )}
                      >
                        {t(`projectTabs.${tab.labelKey}`)}
                      </Link>
                    )
                  })}
                </div>
              )}
    </div>
  )
}

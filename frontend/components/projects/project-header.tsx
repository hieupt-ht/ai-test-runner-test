"use client"

import { Archive, ExternalLink, GitBranch } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { visibleProjectTabs } from "@/lib/project-tabs"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"
import { cn } from "@/lib/utils"

export function ProjectHeader() {
  const t = useTranslations()
  const projectId = useProjectId()
  const pathname = usePathname()
  const { data: project, isLoading, isError } = useProject(projectId)

  if (isLoading) return <Skeleton className="h-24 w-full" />
  if (isError || !project) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-muted-foreground">
          {t("projects.notFound")}
        </CardContent>
      </Card>
    )
  }

  const sheetUrl = `https://docs.google.com/spreadsheets/d/${project.spreadsheet_id}`

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-2xl font-semibold">{project.name}</h2>
          {project.archived && (
            <Badge variant="secondary">
              <Archive /> {t("projects.archived")}
            </Badge>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          <span className="flex items-center gap-1 font-mono text-xs">
            <GitBranch className="size-3.5" />
            {project.repo_full_name}@{project.branch}
          </span>
          <a
            href={sheetUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 hover:text-foreground hover:underline"
          >
            <ExternalLink className="size-3.5" />
            {t("projects.spreadsheetLink")}
          </a>
        </div>
      </div>

      {project.archived && (
        <p className="rounded-lg border bg-muted/50 p-3 text-sm">{t("projects.archivedBanner")}</p>
      )}

      <nav className="flex gap-1 overflow-x-auto border-b">
        {visibleProjectTabs(project.permissions).map((tab) => {
          const href = `/projects/${project.id}/${tab.segment}`
          const isActive = pathname.startsWith(href)
          return (
            <Link
              key={tab.segment}
              href={href}
              className={cn(
                "-mb-px border-b-2 px-3 py-2 text-sm whitespace-nowrap transition-colors",
                isActive
                  ? "border-primary font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {t(`projectTabs.${tab.labelKey}`)}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}

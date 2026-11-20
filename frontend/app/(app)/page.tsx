"use client"

import { ClipboardCheck, Clock3, FolderKanban, RotateCcw, TestTube2 } from "lucide-react"
import { useTranslations } from "next-intl"

import { LazyPassFailChart } from "@/components/charts/lazy"
import { ProgressList } from "@/components/charts/progress-list"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ResultItem } from "@/lib/api/types"
import { useMe } from "@/lib/use-me"
import { useOverview } from "@/lib/use-overview"
import { useMyAssignments } from "@/lib/use-project-data"
import { useProjects } from "@/lib/use-projects"
import { useMyDashboard } from "@/lib/use-stats"

const ACTIVE_STATUSES = new Set(["TODO", "WRITING", "IN_REVIEW"])
const DAY_IN_MS = 24 * 60 * 60 * 1000

function daysUntil(deadline: string, today = new Date()) {
  const [year, month, day] = deadline.split("-").map(Number)
  const target = Date.UTC(year, month - 1, day)
  const current = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((target - current) / DAY_IN_MS)
}

function MetricCard({
  title,
  value,
  description,
  icon: Icon,
}: {
  title: string
  value: number
  description: string
  icon: typeof ClipboardCheck
}) {
  return (
    <Card>
      <CardHeader className="grid grid-cols-[1fr_auto] items-center">
        <CardTitle>{title}</CardTitle>
        <Icon aria-hidden="true" className="size-5 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

function LatestResultCard({ result, emptyText }: { result?: ResultItem; emptyText: string }) {
  const t = useTranslations("overview")

  return (
    <Card>
      <CardHeader className="grid grid-cols-[1fr_auto] items-center">
        <CardTitle>{t("latestResult")}</CardTitle>
        <TestTube2 aria-hidden="true" className="size-5 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {result ? (
          <div className="space-y-2">
            <p className="text-2xl font-semibold">{result.status}</p>
            <p className="text-sm text-muted-foreground">{result.case_title}</p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{emptyText}</p>
        )}
      </CardContent>
    </Card>
  )
}

export default function OverviewPage() {
  const t = useTranslations("overview")
  const { user } = useMe()
  const { data: assignments = [] } = useMyAssignments(user?.role === "TESTER")
  const { data: projects = [] } = useProjects(user?.role === "ADMIN")

  const canSeeResults = user?.role === "QA_LEAD" || user?.role === "ADMIN"
  const { data: overview } = useOverview(canSeeResults)
  // Đồ thị tiến độ dành cho mọi vai trò (backend chỉ trả các dự án mình được xem)
  const { data: dashboard } = useMyDashboard()
  const hasDashboard = (dashboard?.projects.length ?? 0) > 0

  const activeAssignments = assignments.filter((assignment) => ACTIVE_STATUSES.has(assignment.status))
  const dueSoon = activeAssignments.filter((assignment) => {
    const remainingDays = daysUntil(assignment.deadline)
    return remainingDays >= 0 && remainingDays <= 3
  })
  const returnedCases = assignments.reduce(
    (total, assignment) => total + (assignment.returned_cases?.length ?? 0),
    0,
  )

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("greeting", { name: user?.name ?? "" })}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("description")}</p>
      </div>

      {user?.role === "TESTER" && (
        <section aria-label={t("testerSection")} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetricCard
            title={t("activeWork")}
            value={activeAssignments.length}
            description={t("activeWorkDescription")}
            icon={ClipboardCheck}
          />
          <MetricCard
            title={t("dueSoon")}
            value={dueSoon.length}
            description={t("dueSoonDescription")}
            icon={Clock3}
          />
          <MetricCard
            title={t("returnedCases")}
            value={returnedCases}
            description={t("returnedCasesDescription")}
            icon={RotateCcw}
          />
        </section>
      )}

      {user?.role === "QA_LEAD" && (
        <section aria-label={t("qaSection")} className="grid gap-4 md:grid-cols-2">
          <MetricCard
            title={t("pendingReview")}
            value={overview?.pending_review ?? 0}
            description={t("pendingReviewDescription")}
            icon={ClipboardCheck}
          />
          <LatestResultCard result={overview?.latest_result ?? undefined} emptyText={t("noResults")} />
        </section>
      )}

      {user?.role === "ADMIN" && (
        <section aria-label={t("adminSection")} className="grid gap-4 md:grid-cols-2">
          <MetricCard
            title={t("projectCount")}
            value={projects.length}
            description={projects.length ? t("projectCountDescription") : t("noProjects")}
            icon={FolderKanban}
          />
          <LatestResultCard result={overview?.latest_result ?? undefined} emptyText={t("noResults")} />
        </section>
      )}

      {hasDashboard && dashboard && (
        <section className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>{t("projectProgress")}</CardTitle>
            </CardHeader>
            <CardContent>
              <ProgressList
                items={dashboard.projects.map((project) => ({
                  id: project.project_id,
                  label: project.project_name,
                  done: project.done,
                  total: project.total,
                }))}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("recentResults")}</CardTitle>
            </CardHeader>
            <CardContent>
              <LazyPassFailChart days={dashboard.daily} />
            </CardContent>
          </Card>
        </section>
      )}

      {user?.role === "VIEWER" && !hasDashboard && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            {t("viewerEmpty")}
          </CardContent>
        </Card>
      )}
    </main>
  )
}

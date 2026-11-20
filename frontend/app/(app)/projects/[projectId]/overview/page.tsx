"use client"

import { useTranslations } from "next-intl"

import { ProjectLeaderboards } from "@/components/leaderboard/project-leaderboards"
import { ProgressList } from "@/components/charts/progress-list"
import { LazyCaseStatusDonut, LazyPassFailChart } from "@/components/charts/lazy"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useProjectId } from "@/lib/use-project-id"
import { useProjectStats } from "@/lib/use-stats"

function StatCard({ title, value }: { title: string; value: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  )
}

export default function ProjectOverviewPage() {
  const t = useTranslations("projectOverview")
  const projectId = useProjectId()
  const { data: stats } = useProjectStats(projectId)

  if (!stats) return <Skeleton className="h-64 w-full" />

  // Chưa có kết quả PASS/FAIL nào thì không có % để hiện
  const passRate = stats.pass_rate === null ? "—" : `${Math.round(stats.pass_rate * 100)}%`

  return (
    <div className="flex flex-col gap-6">
      <section aria-label={t("numbers")} className="grid gap-4 sm:grid-cols-3">
        <StatCard title={t("totalCases")} value={String(stats.total_cases)} />
        <StatCard title={t("passRate")} value={passRate} />
        <StatCard title={t("openBugs")} value={String(stats.open_bugs)} />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("daily")}</CardTitle>
          </CardHeader>
          <CardContent>
            <LazyPassFailChart days={stats.daily} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("caseStatus")}</CardTitle>
          </CardHeader>
          <CardContent>
            <LazyCaseStatusDonut counts={stats.case_status} />
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{t("screens")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ProgressList
            items={stats.screens.map((screen) => ({
              id: screen.screen_id,
              label: screen.screen_name,
              done: screen.done,
              total: screen.total,
            }))}
          />
        </CardContent>
      </Card>

      <ProjectLeaderboards projectId={projectId} />
    </div>
  )
}

"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"

import { LeaderboardCard } from "@/components/leaderboard/leaderboard-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { Period } from "@/lib/api/types"
import { useMe } from "@/lib/use-me"
import { useLeaderboard } from "@/lib/use-stats"

const PERIODS: Period[] = ["week", "month", "all"]

/** Hai bảng xếp hạng của project (viết case, bắt bug) có nút chọn khoảng thời gian. */
export function ProjectLeaderboards({ projectId }: { projectId: string }) {
  const t = useTranslations("leaderboard")
  const { user } = useMe()
  const [period, setPeriod] = useState<Period>("week")
  const { data } = useLeaderboard(projectId, period)

  return (
    <section aria-label={t("section")} className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {PERIODS.map((value) => (
          <Button
            key={value}
            type="button"
            size="sm"
            variant={value === period ? "default" : "outline"}
            aria-pressed={value === period}
            onClick={() => setPeriod(value)}
          >
            {t(`period.${value}`)}
          </Button>
        ))}
      </div>
      {data ? (
        <div className="grid gap-4 md:grid-cols-2">
          <LeaderboardCard title={t("cases")} board={data.cases} meEmail={user?.email ?? ""} />
          <LeaderboardCard title={t("bugs")} board={data.bugs} meEmail={user?.email ?? ""} />
        </div>
      ) : (
        <Skeleton className="h-48 w-full" />
      )}
    </section>
  )
}

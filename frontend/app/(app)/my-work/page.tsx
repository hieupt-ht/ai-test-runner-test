"use client"

import { ArrowRight, ListChecks } from "lucide-react"
import Link from "next/link"
import { useTranslations } from "next-intl"

import { DeadlineBadge, StatusBadge } from "@/components/common/badges"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useMyAssignments } from "@/lib/use-project-data"

export default function MyWorkPage() {
  const t = useTranslations("myWork")
  const tCases = useTranslations("testCases")
  const { data: items = [], isLoading } = useMyAssignments()

  if (isLoading) return <Skeleton className="mx-auto h-48 max-w-4xl" />

  if (items.length === 0) {
    return (
      <Card className="mx-auto max-w-xl">
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex size-12 items-center justify-center rounded-full bg-muted">
            <ListChecks className="size-6 text-muted-foreground" />
          </div>
          <p className="font-medium">{t("empty")}</p>
          <p className="text-sm text-muted-foreground">{t("emptyHint")}</p>
        </CardContent>
      </Card>
    )
  }

  // Danh sách đã được backend sắp xếp theo deadline (gần nhất lên trước).
  return (
    <div className="mx-auto grid max-w-4xl gap-3">
      {items.map((item) => {
        // case_counts là tuỳ chọn trong kiểu sinh ra; thiếu thì coi như 0 hết.
        const counts = item.case_counts ?? {}
        return (
          <Card key={`${item.project_id}-${item.assignment_id}`}>
            <CardContent className="flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
              <Link href={`/projects/${item.project_id}/screens`} className="min-w-0">
                <p className="text-xs text-muted-foreground">{item.project_name}</p>
                <p className="truncate font-medium">
                  {item.screen_name}
                  <span className="ml-2 font-mono text-xs text-muted-foreground">
                    {item.screen_id}
                  </span>
                </p>
                <p className="text-xs text-muted-foreground">
                  {tCases("caseCounts", {
                    draft: counts.DRAFT ?? 0,
                    inReview: counts.IN_REVIEW ?? 0,
                    approved: counts.APPROVED ?? 0,
                  })}
                </p>
              </Link>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={item.status} />
                <DeadlineBadge deadline={item.deadline} />
                <Link
                  href={`/projects/${item.project_id}/test-cases?screen=${item.screen_id}`}
                  className={buttonVariants({ size: "sm" })}
                >
                  {tCases("writeCases")} <ArrowRight />
                </Link>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

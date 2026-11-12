"use client"

import { ArrowRight, ListChecks } from "lucide-react"
import Link from "next/link"
import { useTranslations } from "next-intl"

import { DeadlineBadge, StatusBadge } from "@/components/common/badges"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useMyAssignments } from "@/lib/use-project-data"

export default function MyWorkPage() {
  const t = useTranslations("myWork")
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
      {items.map((item) => (
        <Link
          key={`${item.project_id}-${item.assignment_id}`}
          href={`/projects/${item.project_id}/screens`}
          className="group"
        >
          <Card className="transition-colors group-hover:border-primary/40">
            <CardContent className="flex flex-col gap-2 pt-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">{item.project_name}</p>
                <p className="truncate font-medium">
                  {item.screen_name}
                  <span className="ml-2 font-mono text-xs text-muted-foreground">
                    {item.screen_id}
                  </span>
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={item.status} />
                <DeadlineBadge deadline={item.deadline} />
                <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}

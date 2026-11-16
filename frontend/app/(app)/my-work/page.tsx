"use client"

import { ArrowRight, ListChecks, Undo2 } from "lucide-react"
import Link from "next/link"
import { useState } from "react"
import { useTranslations } from "next-intl"

import { DeadlineBadge, StatusBadge } from "@/components/common/badges"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useMyAssignments } from "@/lib/use-project-data"
import type { MyAssignment } from "@/lib/api/types"

type WorkTab = "active" | "done"
const ACTIVE_STATUSES = new Set<MyAssignment["status"]>(["TODO", "WRITING", "IN_REVIEW"])
const DONE_STATUSES = new Set<MyAssignment["status"]>(["APPROVED", "TESTED"])

export default function MyWorkPage() {
  const t = useTranslations("myWork")
  const tCases = useTranslations("testCases")
  const { data: items = [], isLoading } = useMyAssignments()
  const [tab, setTab] = useState<WorkTab>("active")
  const [includeArchived, setIncludeArchived] = useState(false)
  const activeItems = items.filter((item) => ACTIVE_STATUSES.has(item.status))
  const doneItems = items.filter((item) => DONE_STATUSES.has(item.status))
  const visibleItems = tab === "active" ? activeItems : doneItems

  if (isLoading) return <Skeleton className="mx-auto h-48 max-w-4xl" />

  // Danh sách đã được backend sắp xếp theo deadline (gần nhất lên trước).
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <label className="flex w-fit items-center gap-2 rounded-md border px-3 py-2 text-sm">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(event) => setIncludeArchived(event.target.checked)}
        />
        {tCases("includeArchived")}
      </label>
      <div role="tablist" aria-label={t("title")} className="flex gap-1 border-b">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "active"}
          aria-controls="my-work-panel"
          onClick={() => setTab("active")}
          className="-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground aria-selected:border-primary aria-selected:font-medium aria-selected:text-foreground"
        >
          {t("activeTab")} <span className="ml-1 text-xs">{activeItems.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "done"}
          aria-controls="my-work-panel"
          onClick={() => setTab("done")}
          className="-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground aria-selected:border-primary aria-selected:font-medium aria-selected:text-foreground"
        >
          {t("doneTab")} <span className="ml-1 text-xs">{doneItems.length}</span>
        </button>
      </div>

      <div id="my-work-panel" role="tabpanel" className="grid gap-3">
      {visibleItems.length === 0 ? (
        <Card className="mx-auto w-full max-w-xl">
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-muted">
              <ListChecks className="size-6 text-muted-foreground" />
            </div>
            <p className="font-medium">{t(tab === "active" ? "emptyActive" : "emptyDone")}</p>
            {tab === "active" && <p className="text-sm text-muted-foreground">{t("emptyHint")}</p>}
          </CardContent>
        </Card>
      ) : visibleItems.map((item) => {
        // case_counts là tuỳ chọn trong kiểu sinh ra; thiếu thì coi như 0 hết.
        const counts = item.case_counts ?? {}
        const returned = item.returned_cases ?? []
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
                {returned.length > 0 && (
                  <Badge variant="destructive">
                    {tCases("returnedBadge", { count: returned.length })}
                  </Badge>
                )}
                <StatusBadge status={item.status} />
                <DeadlineBadge deadline={item.deadline} />
                <Link
                  href={`/projects/${item.project_id}/test-cases?screen=${item.screen_id}${
                    includeArchived ? "&include_archived=true" : ""
                  }`}
                  className={buttonVariants({ size: "sm" })}
                >
                  {tCases("writeCases")} <ArrowRight />
                </Link>
              </div>
            </CardContent>
            {returned.length > 0 && (
              <CardContent className="flex flex-col gap-2 border-t pt-4">
                <p className="flex items-center gap-2 text-sm font-medium text-destructive">
                  <Undo2 className="size-4" />
                  {tCases("returnedHeading", { count: returned.length })}
                </p>
                {returned.map((returnedCase) => (
                  <div
                    key={returnedCase.case_id}
                    className="flex flex-col gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        <span className="mr-2 font-mono text-xs text-muted-foreground">
                          {returnedCase.case_id}
                        </span>
                        {returnedCase.title}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {tCases("returnedReason", {
                          by: returnedCase.returned_by,
                          comment: returnedCase.comment,
                        })}
                      </p>
                    </div>
                    <Link
                      href={`/projects/${item.project_id}/test-cases/${returnedCase.case_id}`}
                      className={buttonVariants({ size: "sm", variant: "outline" })}
                    >
                      {tCases("rewrite")} <ArrowRight />
                    </Link>
                  </div>
                ))}
              </CardContent>
            )}
          </Card>
        )
      })}
      </div>
    </div>
  )
}

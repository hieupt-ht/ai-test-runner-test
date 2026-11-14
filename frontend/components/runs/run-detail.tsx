"use client"

import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ResultStatus, RunDetail, RunStatus } from "@/lib/api/types"
import {
  RESULT_STATUSES,
  countResults,
  filterResults,
  isRunActive,
  screenshotUrl,
} from "@/lib/runs/summary"
import { useCancelRun, useRun } from "@/lib/use-runs"
import { cn } from "@/lib/utils"

// Màu trạng thái nhất quán toàn app (spec mục 11): PASS xanh lá, FAIL đỏ, BLOCKED cam, INCONCLUSIVE xám.
const RESULT_COLORS: Record<ResultStatus, string> = {
  PASS: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
  FAIL: "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-200",
  BLOCKED: "bg-orange-100 text-orange-800 dark:bg-orange-500/20 dark:text-orange-200",
  INCONCLUSIVE: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/20 dark:text-zinc-300",
}

const RUN_COLORS: Record<RunStatus, string> = {
  QUEUED: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/20 dark:text-zinc-300",
  RUNNING: "bg-sky-100 text-sky-800 dark:bg-sky-500/20 dark:text-sky-200",
  COMPLETED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
  FAILED: "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-200",
  CANCELLED: "bg-zinc-100 text-zinc-500 dark:bg-zinc-500/10",
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const t = useTranslations("runs.status")
  return (
    <Badge variant="outline" className={cn("border-transparent", RUN_COLORS[status])}>
      {t(status)}
    </Badge>
  )
}

type ViewProps = {
  projectId: string
  run: RunDetail
  canCancel: boolean
  cancelling: boolean
  onCancel: () => void
}

/** Phần hiển thị thuần của một lần chạy (dữ liệu truyền vào, không tự gọi API). */
export function RunDetailView({ projectId, run, canCancel, cancelling, onCancel }: ViewProps) {
  const t = useTranslations("runs.detail")
  const [filter, setFilter] = useState<ResultStatus | "ALL">("ALL")
  const counts = countResults(run.results)
  const visible = filterResults(run.results, filter)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-mono text-sm font-semibold">{run.id}</h3>
        <RunStatusBadge status={run.status} />
        <span className="text-xs text-muted-foreground">{run.triggered_by_name}</span>
        <span className="text-xs text-muted-foreground" title={t("progress")}>
          {run.results.length}/{run.total}
        </span>
        {canCancel && isRunActive(run.status) && (
          <Button variant="outline" size="sm" disabled={cancelling} onClick={onCancel}>
            {cancelling ? t("cancelling") : t("cancel")}
          </Button>
        )}
      </div>

      {run.note && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm">
          <p className="mb-1 text-xs font-medium text-destructive">{t("noteTitle")}</p>
          <p className="whitespace-pre-wrap">{run.note}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          variant={filter === "ALL" ? "secondary" : "ghost"}
          size="sm"
          aria-label={t("filterAll")}
          aria-pressed={filter === "ALL"}
          onClick={() => setFilter("ALL")}
        >
          {run.results.length}
        </Button>
        {RESULT_STATUSES.map((status) => (
          <div key={status} className="flex items-center gap-1" aria-label={`${status}: ${counts[status]}`}>
            <Button
              variant={filter === status ? "secondary" : "ghost"}
              size="sm"
              aria-label={t("filter", { status })}
              aria-pressed={filter === status}
              onClick={() => setFilter(status)}
            >
              <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium", RESULT_COLORS[status])}>
                {status}
              </span>
              <span aria-hidden>{counts[status]}</span>
            </Button>
          </div>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("noResults")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map((result) => (
            <li key={result.id} className="flex flex-col gap-1.5 rounded-lg border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant="outline"
                  className={cn("border-transparent", RESULT_COLORS[result.status])}
                >
                  {result.status}
                </Badge>
                <span className="font-mono text-xs text-muted-foreground">
                  {result.test_case_id}
                </span>
                <span className="font-medium">{result.test_case_title}</span>
                {result.failed_step !== null && (
                  <span className="text-xs text-muted-foreground">
                    {t("step", { n: result.failed_step })}
                  </span>
                )}
              </div>
              {result.reason && (
                <p className="whitespace-pre-wrap text-muted-foreground">{result.reason}</p>
              )}
              {result.screenshot && (
                <a
                  href={screenshotUrl(projectId, run.id, result.screenshot)}
                  target="_blank"
                  rel="noreferrer"
                  title={t("openScreenshot")}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={screenshotUrl(projectId, run.id, result.screenshot)}
                    alt={t("screenshot", { id: result.test_case_id })}
                    loading="lazy"
                    className="max-h-64 w-auto max-w-full rounded border"
                  />
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Tự tải một lần chạy (làm mới mỗi 3 giây khi chưa xong) và gắn nút Huỷ. */
export function RunDetailPanel({
  projectId,
  runId,
  canCancel,
}: {
  projectId: string
  runId: string
  canCancel: boolean
}) {
  const t = useTranslations("runs.detail")
  const query = useRun(projectId, runId)
  const cancel = useCancelRun(projectId)

  if (query.isLoading) return <Skeleton className="h-32 w-full" />
  if (query.isError || !query.data) {
    return (
      <p className="text-sm text-destructive">
        {t("loadFailed", { message: query.error?.message ?? "" })}
      </p>
    )
  }

  async function handleCancel() {
    try {
      await cancel.mutateAsync(runId)
      toast.success(t("cancelRequested"))
    } catch (error) {
      toast.error(t("cancelFailed", { message: error instanceof Error ? error.message : "" }))
    }
  }

  return (
    <RunDetailView
      projectId={projectId}
      run={query.data}
      canCancel={canCancel}
      cancelling={cancel.isPending}
      onCancel={() => void handleCancel()}
    />
  )
}

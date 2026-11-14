"use client"

import { useFormatter, useTranslations } from "next-intl"

import { RunStatusBadge } from "@/components/runs/run-detail"
import type { RunView } from "@/lib/api/types"
import { cn } from "@/lib/utils"

type Props = {
  runs: RunView[]
  selectedId: string | undefined
  onSelect: (runId: string) => void
}

/** Danh sách các lần chạy, mới nhất trước. Bấm một dòng để xem chi tiết. */
export function RunList({ runs, selectedId, onSelect }: Props) {
  const t = useTranslations("runs.list")
  const format = useFormatter()

  if (runs.length === 0) return <p className="text-sm text-muted-foreground">{t("empty")}</p>

  return (
    <ul className="flex flex-col gap-1" aria-label={t("title")}>
      {runs.map((run) => (
        <li key={run.id}>
          <button
            type="button"
            onClick={() => onSelect(run.id)}
            aria-current={run.id === selectedId}
            className={cn(
              "flex w-full flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm hover:bg-muted",
              run.id === selectedId && "border-primary bg-muted",
            )}
          >
            <span className="font-mono text-xs font-semibold">{run.id}</span>
            <RunStatusBadge status={run.status} />
            <span className="text-xs text-muted-foreground">
              {t("casesDone", { passed: run.passed, failed: run.failed })}
            </span>
            <span className="ml-auto text-xs text-muted-foreground">
              {t("by", { name: run.triggered_by_name })} ·{" "}
              {format.dateTime(new Date(run.started_at), { dateStyle: "short", timeStyle: "short" })}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}

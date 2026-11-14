"use client"

import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import type { Priority, RunScope, RunView, Severity } from "@/lib/api/types"
import { isRunActive } from "@/lib/runs/summary"
import { useScreens } from "@/lib/use-project-data"
import { usePreviewRun, useStartRun } from "@/lib/use-runs"

const PRIORITIES: Priority[] = ["P1", "P2", "P3"]
const SEVERITIES: Severity[] = ["LOW", "MEDIUM", "HIGH"]

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((value) => value !== item) : [...list, item]
}

type Props = {
  projectId: string
  /** Các lần chạy hiện có, để khoá nút khi đang có run chưa xong. */
  runs: RunView[]
  onStarted: (runId: string) => void
}

/** Chọn phạm vi, xem trước số case sẽ chạy rồi bấm Chạy. Chỉ hiện cho người có quyền TRIGGER_RUN. */
export function RunLauncher({ projectId, runs, onStarted }: Props) {
  const t = useTranslations("runs.launcher")
  const tCase = useTranslations("testCases")
  const [scope, setScope] = useState<Required<RunScope>>({ screen_ids: [], priorities: [], severities: [] })
  const screens = useScreens(projectId).data ?? []
  const preview = usePreviewRun(projectId, scope)
  const start = useStartRun(projectId)
  const busy = runs.some((run) => isRunActive(run.status))
  const count = preview.data?.count

  async function handleStart() {
    try {
      const run = await start.mutateAsync(scope)
      toast.success(t("started", { id: run.id }))
      onStarted(run.id)
    } catch (error) {
      toast.error(t("startFailed", { message: error instanceof Error ? error.message : "" }))
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-3">
      <h2 className="text-sm font-semibold">{t("title")}</h2>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:gap-6">
        <fieldset className="flex min-w-0 flex-col gap-1">
          <legend className="mb-1 text-xs font-medium text-muted-foreground">{t("screens")}</legend>
          {screens.length === 0 && <p className="text-xs text-muted-foreground">{t("allScreens")}</p>}
          <div className="flex max-h-32 flex-col gap-1 overflow-y-auto">
            {screens.map((screen) => (
              <label key={screen.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={scope.screen_ids.includes(screen.id)}
                  onChange={() =>
                    setScope({ ...scope, screen_ids: toggle(scope.screen_ids, screen.id) })
                  }
                />
                <span className="truncate">
                  {screen.id} · {screen.name}
                </span>
              </label>
            ))}
          </div>
          {scope.screen_ids.length === 0 && screens.length > 0 && (
            <p className="text-xs text-muted-foreground">{t("allScreens")}</p>
          )}
        </fieldset>

        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-xs font-medium text-muted-foreground">{t("priority")}</legend>
          {PRIORITIES.map((priority) => (
            <label key={priority} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={scope.priorities.includes(priority)}
                onChange={() => setScope({ ...scope, priorities: toggle(scope.priorities, priority) })}
              />
              {priority}
            </label>
          ))}
        </fieldset>

        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-xs font-medium text-muted-foreground">{t("severity")}</legend>
          {SEVERITIES.map((severity) => (
            <label key={severity} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={scope.severities.includes(severity)}
                onChange={() => setScope({ ...scope, severities: toggle(scope.severities, severity) })}
              />
              {tCase(`severity.${severity}`)}
            </label>
          ))}
        </fieldset>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          disabled={busy || start.isPending || !count}
          onClick={() => void handleStart()}
        >
          {t("start")}
        </Button>
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {preview.isLoading ? t("counting") : count === 0 ? t("none") : count !== undefined && t("count", { count })}
        </p>
      </div>
      {busy && <p className="text-xs text-muted-foreground">{t("busy")}</p>}
    </section>
  )
}

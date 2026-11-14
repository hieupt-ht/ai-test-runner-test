"use client"

import { useTranslations } from "next-intl"
import { Suspense, useState } from "react"

import { RunDetailPanel } from "@/components/runs/run-detail"
import { RunLauncher } from "@/components/runs/run-launcher"
import { RunList } from "@/components/runs/run-list"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"
import { useRuns } from "@/lib/use-runs"

// useProjectId (useParams) cần nằm trong <Suspense> vì đang bật cacheComponents.
export default function RunsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-48 w-full" />}>
      <Runs />
    </Suspense>
  )
}

function Runs() {
  const t = useTranslations("runs.list")
  const projectId = useProjectId()
  const { data: project } = useProject(projectId)
  const runsQuery = useRuns(projectId)
  const [selected, setSelected] = useState<string | undefined>(undefined)

  const runs = runsQuery.data ?? []
  // Chưa chọn thì xem lần chạy mới nhất.
  const selectedId = selected ?? runs[0]?.id
  const canTrigger = Boolean(project?.permissions.includes("TRIGGER_RUN")) && !project?.archived

  if (runsQuery.isLoading) return <Skeleton className="h-48 w-full" />
  if (runsQuery.isError) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="text-sm text-destructive">
          {t("loadFailed", { message: runsQuery.error.message })}
        </p>
        <Button variant="outline" size="sm" onClick={() => void runsQuery.refetch()}>
          {t("retry")}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {canTrigger && <RunLauncher projectId={projectId} runs={runs} onStarted={setSelected} />}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">{t("title")}</h2>
          <RunList runs={runs} selectedId={selectedId} onSelect={setSelected} />
        </div>
        {selectedId && (
          <RunDetailPanel projectId={projectId} runId={selectedId} canCancel={canTrigger} />
        )}
      </div>
    </div>
  )
}

"use client"

import { Suspense, useMemo, useState } from "react"
import { useTranslations } from "next-intl"
import { useRouter, useSearchParams } from "next/navigation"

import { CheckCircle2, ChevronDown, ChevronRight, Loader2, TriangleAlert, XCircle } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useProjectId } from "@/lib/use-project-id"
import { cn } from "@/lib/utils"
import { useMe } from "@/lib/use-me"
import { useRequestRerun, useResults } from "@/lib/use-results"
import type { ResultItem, ResultStatus } from "@/lib/api/types"

const STATUSES: ResultStatus[] = ["PASS", "FAIL", "BLOCKED", "INCONCLUSIVE"]

const GROUPS = ["FAIL", "BLOCKED", "PASS"] as const

function safeEvidenceUrl(value: string): string | null {
  try {
    const url = new URL(value)
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null
  } catch {
    return null
  }
}

type ScreenSummary = {
  id: string
  name: string
  pass: number
  fail: number
  blocked: number
}

function summarizeScreens(results: ResultItem[]): ScreenSummary[] {
  const summaries = new Map<string, ScreenSummary>()
  for (const result of results) {
    const summary = summaries.get(result.screen_id) ?? {
      id: result.screen_id,
      name: result.screen_name,
      pass: 0,
      fail: 0,
      blocked: 0,
    }
    if (result.status === "PASS") summary.pass += 1
    if (result.status === "FAIL") summary.fail += 1
    if (result.status === "BLOCKED" || result.status === "INCONCLUSIVE") {
      summary.blocked += 1
    }
    summaries.set(result.screen_id, summary)
  }
  return [...summaries.values()]
}

const COUNT_STYLES = {
  PASS: {
    icon: CheckCircle2,
    color: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
  },
  FAIL: {
    icon: XCircle,
    color: "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-200",
  },
  BLOCKED: {
    icon: TriangleAlert,
    color: "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200",
  },
} as const

/** Một ô đếm: icon + số, tô màu theo trạng thái; số 0 thì làm mờ. */
function CountBadge({
  kind,
  count,
  label,
}: {
  kind: keyof typeof COUNT_STYLES
  count: number
  label: string
}) {
  const { icon: Icon, color } = COUNT_STYLES[kind]
  return (
    <Badge
      variant="outline"
      aria-label={`${label}: ${count}`}
      className={cn("border-transparent", count > 0 ? color : "bg-muted text-muted-foreground")}
    >
      <Icon aria-hidden />
      {count}
    </Badge>
  )
}

function ResultsContent() {
  const t = useTranslations("results")
  const projectId = useProjectId()
  const router = useRouter()
  const searchParams = useSearchParams()
  const screenId = searchParams.get("screen") || undefined
  const [status, setStatus] = useState<ResultStatus | undefined>()
  const [collapsed, setCollapsed] = useState<ResultStatus[]>(["PASS"])
  const { data = [], isLoading, isError } = useResults(projectId, undefined, screenId)
  const { user } = useMe()
  const rerun = useRequestRerun(projectId)
  // Chỉ QA Lead/Admin được yêu cầu chạy lại
  const canRerun = user?.role === "QA_LEAD" || user?.role === "ADMIN"
  const screenSummaries = useMemo(() => summarizeScreens(data), [data])
  const groups = useMemo(() => {
    const rows = status ? data.filter((item) => item.status === status) : data
    return {
      FAIL: rows.filter((item) => item.status === "FAIL"),
      BLOCKED: rows.filter((item) => item.status === "BLOCKED" || item.status === "INCONCLUSIVE"),
      PASS: rows.filter((item) => item.status === "PASS"),
    }
  }, [data, status])
  const counts = {
    PASS: data.filter((item) => item.status === "PASS").length,
    FAIL: data.filter((item) => item.status === "FAIL").length,
    BLOCKED: data.filter((item) => item.status === "BLOCKED" || item.status === "INCONCLUSIVE").length,
  }
  const resultsPath = `/projects/${projectId}/results`
  const screenName = data[0]?.screen_name ?? screenId

  function requestRerun(caseId: string) {
    rerun.mutate(caseId, {
      onSuccess: () => toast.success(t("rerunSuccess")),
      onError: (error) => toast.error(error instanceof Error && error.message ? error.message : t("rerunError")),
    })
  }

  function openScreen(id: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set("screen", id)
    setStatus(undefined)
    router.push(`${resultsPath}?${params.toString()}`)
  }

  function showAllScreens() {
    const params = new URLSearchParams(searchParams.toString())
    params.delete("screen")
    setStatus(undefined)
    const query = params.toString()
    router.push(query ? `${resultsPath}?${query}` : resultsPath)
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          {screenId && (
            <button
              type="button"
              onClick={showAllScreens}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              ← {t("allScreens")}
            </button>
          )}
          {screenId && <h2 className="text-lg font-semibold">{screenName}</h2>}
        </div>
        {screenId && (
          <label className="flex items-center gap-2 text-sm">
            <span>{t("filterStatus")}</span>
            <select
              aria-label={t("filterStatus")}
              value={status ?? "all"}
              onChange={(event) =>
                setStatus(event.target.value === "all" ? undefined : (event.target.value as ResultStatus))
              }
              className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm"
            >
              <option value="all">{t("all")}</option>
              {STATUSES.map((item) => (
                <option key={item} value={item}>
                  {t(`status.${item}`)}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {isLoading ? (
        <Skeleton className="h-48 w-full" aria-label={t("loading")} />
      ) : isError ? (
        <p role="alert" className="rounded-lg border py-10 text-center text-sm text-destructive">
          {t("error")}
        </p>
      ) : data.length === 0 ? (
        <p className="rounded-lg border py-10 text-center text-sm text-muted-foreground">
          {t("empty")}
        </p>
      ) : !screenId ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {screenSummaries.map((summary) => (
            <Card
              key={summary.id}
              role="button"
              tabIndex={0}
              onClick={() => openScreen(summary.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault()
                  openScreen(summary.id)
                }
              }}
              className="cursor-pointer transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <CardHeader>
                <CardTitle className="text-lg font-semibold">{summary.name}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <CountBadge kind="PASS" count={summary.pass} label={t("status.PASS")} />
                  <CountBadge kind="FAIL" count={summary.fail} label={t("status.FAIL")} />
                  <CountBadge kind="BLOCKED" count={summary.blocked} label={t("status.BLOCKED")} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="rounded-lg border bg-muted/30 px-4 py-3 text-sm font-medium" aria-live="polite">
            {t("summary", counts)}
          </p>
          {GROUPS.map((group) => {
            const rows = groups[group]
            if (rows.length === 0) return null
            const isCollapsed = collapsed.includes(group)
            return (
              <section key={group} className="overflow-hidden rounded-lg border">
                <button
                  type="button"
                  aria-expanded={!isCollapsed}
                  onClick={() => setCollapsed((items) =>
                    isCollapsed ? items.filter((item) => item !== group) : [...items, group],
                  )}
                  className="flex w-full items-center gap-2 bg-muted/40 px-4 py-3 text-left font-semibold"
                >
                  {isCollapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
                  {t(`status.${group}`)}: {rows.length}
                </button>
                {!isCollapsed && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-28">{t("caseId")}</TableHead>
                        <TableHead>{t("caseTitle")}</TableHead>
                        <TableHead>{t("reasonColumn")}</TableHead>
                        <TableHead>{t("failedStepColumn")}</TableHead>
                        <TableHead>{t("evidence")}</TableHead>
                        {canRerun && <TableHead className="w-32 text-right">{t("actionsColumn")}</TableHead>}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((result) => {
                        const evidenceUrl = result.evidence ? safeEvidenceUrl(result.evidence) : null
                        return (
                          <TableRow key={`${result.case_id}-${result.run_id}`}>
                            <TableCell className="font-mono text-xs text-muted-foreground">{result.case_id}</TableCell>
                            <TableCell className="font-medium">{result.case_title}</TableCell>
                            <TableCell className="max-w-sm whitespace-normal">{result.reason || "—"}</TableCell>
                            <TableCell>
                              {result.failed_step === null ? "—" : t("failedStep", { step: result.failed_step })}
                            </TableCell>
                            <TableCell>
                              {evidenceUrl && (
                                <a
                                  href={evidenceUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="underline-offset-2 hover:underline"
                                >
                                  {t("evidence")}
                                </a>
                              )}
                            </TableCell>
                            {canRerun && (
                              <TableCell className="text-right">
                                {result.status !== "PASS" && (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    disabled={rerun.isPending}
                                    onClick={() => requestRerun(result.case_id)}
                                  >
                                    {rerun.isPending && rerun.variables === result.case_id ? (
                                      <>
                                        <Loader2 className="animate-spin" aria-hidden />
                                        {t("rerunPending")}
                                      </>
                                    ) : (
                                      t("rerun")
                                    )}
                                  </Button>
                                )}
                              </TableCell>
                            )}
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                )}
              </section>
            )
          })}
        </div>
      )}
    </section>
  )
}

export default function ResultsPage() {
  return (
    <Suspense fallback={null}>
      <ResultsContent />
    </Suspense>
  )
}

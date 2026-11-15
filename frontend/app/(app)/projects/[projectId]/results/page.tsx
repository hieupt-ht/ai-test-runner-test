"use client"

import { Suspense, useMemo, useState } from "react"
import { useTranslations } from "next-intl"
import { useRouter, useSearchParams } from "next/navigation"

import { ChevronDown, ChevronRight, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useProjectId } from "@/lib/use-project-id"
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
          <h1 className="text-xl font-semibold">{screenId ? screenName : t("title")}</h1>
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
              className="h-9 rounded-lg border border-input bg-background px-3"
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
        <p className="py-8 text-center text-sm text-muted-foreground">{t("loading")}</p>
      ) : isError ? (
        <p role="alert" className="py-8 text-center text-sm text-destructive">
          {t("error")}
        </p>
      ) : data.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">{t("empty")}</p>
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
                <Badge
                  variant={summary.fail > 0 ? "destructive" : summary.blocked > 0 ? "secondary" : "default"}
                  className={
                    summary.fail === 0 && summary.blocked === 0
                      ? "bg-emerald-600 text-white"
                      : undefined
                  }
                >
                  ✅ {summary.pass} · ❌ {summary.fail} · ⚠️ {summary.blocked}
                </Badge>
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
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[640px] text-left text-sm">
                      <thead className="bg-muted/20 text-muted-foreground">
                        <tr>
                          <th className="px-4 py-2">{t("caseId")}</th>
                          <th className="px-4 py-2">{t("caseTitle")}</th>
                          <th className="px-4 py-2">{t("reasonColumn")}</th>
                          <th className="px-4 py-2">{t("failedStepColumn")}</th>
                          <th className="px-4 py-2">{t("evidence")}</th>
                          {canRerun && <th className="px-4 py-2">{t("actionsColumn")}</th>}
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {rows.map((result) => {
                          const evidenceUrl = result.evidence ? safeEvidenceUrl(result.evidence) : null
                          return (
                            <tr key={`${result.case_id}-${result.run_id}`}>
                              <td className="px-4 py-3 font-mono text-xs">{result.case_id}</td>
                              <td className="px-4 py-3">{result.case_title}</td>
                              <td className="max-w-sm px-4 py-3">{result.reason || "—"}</td>
                              <td className="px-4 py-3">
                                {result.failed_step === null ? "—" : t("failedStep", { step: result.failed_step })}
                              </td>
                              <td className="px-4 py-3">
                                {evidenceUrl && (
                                  <a href={evidenceUrl} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-4">
                                    {t("evidence")}
                                  </a>
                                )}
                              </td>
                              {canRerun && (
                                <td className="px-4 py-3">
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
                                          <Loader2 className="size-4 animate-spin" aria-hidden />
                                          {t("rerunPending")}
                                        </>
                                      ) : (
                                        t("rerun")
                                      )}
                                    </Button>
                                  )}
                                </td>
                              )}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
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

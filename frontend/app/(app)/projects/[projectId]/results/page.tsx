"use client"

import { useMemo, useState } from "react"
import { useTranslations } from "next-intl"

import { ChevronDown, ChevronRight } from "lucide-react"
import { useProjectId } from "@/lib/use-project-id"
import { useResults } from "@/lib/use-results"
import type { ResultStatus } from "@/lib/api/types"

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

export default function ResultsPage() {
  const t = useTranslations("results")
  const projectId = useProjectId()
  const [status, setStatus] = useState<ResultStatus | undefined>()
  const [collapsed, setCollapsed] = useState<ResultStatus[]>(["PASS"])
  const { data = [], isLoading, isError } = useResults(projectId, status)
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

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold">{t("title")}</h1>
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
      </div>

      {isLoading ? (
        <p className="py-8 text-center text-sm text-muted-foreground">{t("loading")}</p>
      ) : isError ? (
        <p role="alert" className="py-8 text-center text-sm text-destructive">
          {t("error")}
        </p>
      ) : data.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">{t("empty")}</p>
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

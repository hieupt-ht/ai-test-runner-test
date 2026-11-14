"use client"

import { useState } from "react"
import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useProjectId } from "@/lib/use-project-id"
import { useResults } from "@/lib/use-results"
import type { ResultStatus } from "@/lib/api/types"

const STATUSES: ResultStatus[] = ["PASS", "FAIL", "BLOCKED", "INCONCLUSIVE"]

const statusStyles: Record<ResultStatus, string> = {
  PASS: "border-emerald-600/30 bg-emerald-600/10 text-emerald-700 dark:text-emerald-400",
  FAIL: "border-destructive/30 bg-destructive/10 text-destructive",
  BLOCKED: "border-amber-600/30 bg-amber-600/10 text-amber-700 dark:text-amber-400",
  INCONCLUSIVE: "border-amber-600/30 bg-amber-600/10 text-amber-700 dark:text-amber-400",
}

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
  const { data = [], isLoading, isError } = useResults(projectId, status)

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
        <div className="grid gap-3">
          {data.map((result) => {
            const evidenceUrl = result.evidence ? safeEvidenceUrl(result.evidence) : null
            return (
              <Card key={`${result.case_id}-${result.run_id}`} size="sm">
                <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
                  <CardTitle className="min-w-0">
                    <span className="mr-2 font-mono text-xs text-muted-foreground">{result.case_id}</span>
                    {result.case_title}
                  </CardTitle>
                  <Badge className={statusStyles[result.status]}>{t(`status.${result.status}`)}</Badge>
                </CardHeader>
                <CardContent className="space-y-2">
                  {result.reason && <p>{result.reason}</p>}
                  {result.failed_step !== null && (
                    <p className="text-sm text-muted-foreground">
                      {t("failedStep", { step: result.failed_step })}
                    </p>
                  )}
                  {evidenceUrl && (
                    <a
                      href={evidenceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-primary underline underline-offset-4"
                    >
                      {t("evidence")}
                    </a>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </section>
  )
}

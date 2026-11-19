"use client"

import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ApiError } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"
import { templateUrl, useImportCases, usePreviewImport } from "@/lib/use-case-import"

type ParseResult = components["schemas"]["ParseResult"]
type Issue = components["schemas"]["ImportIssue"]

type Props = {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Lỗi 422 mang danh sách lỗi từng dòng trong body; lỗi khác (409/503) chỉ có một câu. */
function issuesFromError(error: unknown): Issue[] | null {
  if (error instanceof ApiError && error.status === 422) {
    const errors = (error.body as { errors?: unknown } | undefined)?.errors
    if (Array.isArray(errors)) return errors as Issue[]
  }
  return null
}

/** Xếp theo dòng; lỗi chung của file (row = null) lên đầu. */
function sortByRow(issues: Issue[]): Issue[] {
  return [...issues].sort((a, b) => (a.row ?? 0) - (b.row ?? 0))
}

/** Hộp thoại nhập test case từ file Excel: chọn file → xem trước → nhập. */
export function ImportDialog({ projectId, open, onOpenChange }: Props) {
  const t = useTranslations("testCases.import")
  const preview = usePreviewImport(projectId)
  const importCases = useImportCases(projectId)
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<ParseResult | null>(null)
  const [message, setMessage] = useState<string | null>(null) // câu lỗi chung từ backend

  /** "Dòng 7 · Cột: lỗi"; lỗi chung của file (không có dòng) thì không có tiền tố. */
  function describe(issue: Issue): string {
    if (issue.row === null) return issue.message
    const prefix = t("row", { row: issue.row })
    return issue.column ? `${prefix} · ${issue.column}: ${issue.message}` : `${prefix}: ${issue.message}`
  }

  async function onPickFile(picked: File | undefined) {
    if (!picked) return
    setFile(picked)
    setResult(null)
    setMessage(null)
    try {
      setResult(await preview.mutateAsync(picked))
    } catch (error) {
      const issues = issuesFromError(error)
      if (issues) setResult({ cases: [], errors: issues, warnings: [] })
      else setMessage(error instanceof Error ? error.message : String(error))
    }
  }

  async function onImport() {
    if (!file) return
    setMessage(null)
    try {
      const created = await importCases.mutateAsync(file)
      toast.success(t("success", { count: created.created.length }))
      onOpenChange(false)
    } catch (error) {
      const issues = issuesFromError(error)
      if (issues) setResult({ cases: result?.cases ?? [], errors: issues, warnings: [] })
      else setMessage(error instanceof Error ? error.message : String(error))
    }
  }

  const cases = result?.cases ?? []
  const errors = sortByRow(result?.errors ?? [])
  const warnings = sortByRow(result?.warnings ?? [])
  const steps = cases.reduce((sum, item) => sum + item.step_count, 0)
  const screenCount = new Set(cases.map((item) => item.screen_id)).size
  const busy = preview.isPending || importCases.isPending
  const canSubmit = result !== null && errors.length === 0 && cases.length > 0 && !busy

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="flex flex-col gap-1 text-sm">
              {t("fileLabel")}
              <input
                type="file"
                accept=".xlsx"
                onChange={(event) => void onPickFile(event.target.files?.[0])}
              />
            </label>
            <a href={templateUrl(projectId)} download className="text-sm underline underline-offset-2">
              {t("template")}
            </a>
          </div>

          {preview.isPending && <p className="text-sm text-muted-foreground">{t("checking")}</p>}
          {message && <p className="text-sm text-destructive">{message}</p>}

          {errors.length > 0 && (
            <div className="text-sm text-destructive">
              <p className="font-medium">{t("errorsTitle")}</p>
              <ul className="max-h-40 list-disc overflow-auto pl-5">
                {errors.map((issue, index) => (
                  <li key={index}>{describe(issue)}</li>
                ))}
              </ul>
            </div>
          )}

          {warnings.length > 0 && (
            <div className="text-sm text-amber-700 dark:text-amber-400">
              <p className="font-medium">{t("warningsTitle")}</p>
              <ul className="max-h-32 list-disc overflow-auto pl-5">
                {warnings.map((issue, index) => (
                  <li key={index}>{describe(issue)}</li>
                ))}
              </ul>
            </div>
          )}

          {cases.length > 0 && (
            <>
              <p className="text-sm font-medium">
                {t("summary", { cases: cases.length, steps, screens: screenCount })}
              </p>
              {/* Giới hạn chiều cao để không cuộn cả trang ở màn hình nhỏ */}
              <div className="max-h-[50vh] overflow-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("colGroup")}</TableHead>
                      <TableHead>{t("colScreen")}</TableHead>
                      <TableHead>{t("colTitle")}</TableHead>
                      <TableHead>{t("colSteps")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cases.map((item) => (
                      <TableRow key={`${item.group}-${item.row}`}>
                        <TableCell className="font-mono text-xs">{item.group}</TableCell>
                        <TableCell className="text-xs">
                          {item.screen_id} · {item.screen_name}
                        </TableCell>
                        <TableCell>{item.title}</TableCell>
                        <TableCell>{item.step_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("close")}
          </Button>
          <Button disabled={!canSubmit} onClick={() => void onImport()}>
            {importCases.isPending ? t("importing") : t("submit", { count: cases.length })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

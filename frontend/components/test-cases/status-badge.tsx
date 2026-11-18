"use client"

import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import type { ResultStatus, TestCaseStatus } from "@/lib/api/types"
import { cn } from "@/lib/utils"

const COLORS: Record<TestCaseStatus, string> = {
  DRAFT: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/20 dark:text-zinc-300",
  IN_REVIEW: "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200",
  APPROVED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
  TESTED: "bg-violet-100 text-violet-800 dark:bg-violet-500/20 dark:text-violet-200",
  ARCHIVED: "bg-zinc-100 text-zinc-500 dark:bg-zinc-500/10",
  DEPRECATED: "bg-zinc-100 text-zinc-500 line-through opacity-60 dark:bg-zinc-500/10",
}

export function CaseStatusBadge({
  status,
  lastResult,
}: {
  status: TestCaseStatus
  /** Kết quả lần chạy gần nhất; chỉ hiện khi case đang "Đã kiểm thử". */
  lastResult?: ResultStatus
}) {
  const t = useTranslations("testCases.status")
  const tr = useTranslations("testCases.lastResult")
  const showResult = status === "TESTED" && lastResult !== undefined
  return (
    <Badge variant="outline" className={cn("border-transparent", COLORS[status])}>
      {showResult ? `${t(status)} · ${tr(lastResult)}` : t(status)}
    </Badge>
  )
}

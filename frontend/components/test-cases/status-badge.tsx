"use client"

import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import type { TestCaseStatus } from "@/lib/api/types"
import { cn } from "@/lib/utils"

const COLORS: Record<TestCaseStatus, string> = {
  DRAFT: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/20 dark:text-zinc-300",
  IN_REVIEW: "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200",
  APPROVED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
  DEPRECATED: "bg-zinc-100 text-zinc-500 line-through opacity-60 dark:bg-zinc-500/10",
}

export function CaseStatusBadge({ status }: { status: TestCaseStatus }) {
  const t = useTranslations("testCases.status")
  return (
    <Badge variant="outline" className={cn("border-transparent", COLORS[status])}>
      {t(status)}
    </Badge>
  )
}

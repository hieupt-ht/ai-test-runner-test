"use client"

import { CalendarClock } from "lucide-react"
import { useFormatter, useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import type { AssignmentStatus } from "@/lib/api/types"
import { deadlineState, todayInVietnam, type DeadlineState } from "@/lib/deadline"
import { cn } from "@/lib/utils"

const DEADLINE_COLORS: Record<DeadlineState, string> = {
  overdue: "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-200",
  "due-soon": "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200",
  ok: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/20 dark:text-zinc-300",
}

const DEADLINE_LABEL_KEYS: Record<DeadlineState, string> = {
  overdue: "overdue",
  "due-soon": "dueSoon",
  ok: "ok",
}

/** Ngày deadline, tô đỏ khi quá hạn và cam khi còn ≤ 3 ngày. */
export function DeadlineBadge({ deadline }: { deadline: string }) {
  const t = useTranslations("deadline")
  const format = useFormatter()
  const state = deadlineState(deadline, todayInVietnam())
  return (
    <Badge
      variant="outline"
      className={cn("border-transparent", DEADLINE_COLORS[state])}
      title={t(DEADLINE_LABEL_KEYS[state])}
    >
      <CalendarClock />
      {format.dateTime(new Date(`${deadline}T00:00:00`), { dateStyle: "medium" })}
    </Badge>
  )
}

const STATUS_COLORS: Record<AssignmentStatus, string> = {
  TODO: "bg-zinc-100 text-zinc-700 dark:bg-zinc-500/20 dark:text-zinc-300",
  WRITING: "bg-sky-100 text-sky-800 dark:bg-sky-500/20 dark:text-sky-200",
  IN_REVIEW: "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200",
  APPROVED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
  TESTED: "bg-violet-100 text-violet-800 dark:bg-violet-500/20 dark:text-violet-200",
}

export function StatusBadge({ status }: { status: AssignmentStatus }) {
  const t = useTranslations("statuses")
  return (
    <Badge variant="outline" className={cn("border-transparent", STATUS_COLORS[status])}>
      {t(status)}
    </Badge>
  )
}

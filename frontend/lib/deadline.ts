export type DeadlineState = "overdue" | "due-soon" | "ok"

const DUE_SOON_DAYS = 3
const MS_PER_DAY = 24 * 60 * 60 * 1000

/** Số ngày từ `from` tới `to` (đều dạng YYYY-MM-DD), tính theo lịch, không lệch múi giờ. */
function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / MS_PER_DAY)
}

export function deadlineState(deadline: string, today: string): DeadlineState {
  const daysLeft = daysBetween(today, deadline)
  if (daysLeft < 0) return "overdue"
  if (daysLeft <= DUE_SOON_DAYS) return "due-soon"
  return "ok"
}

/** Hôm nay theo giờ Việt Nam, dạng YYYY-MM-DD (giống cách backend so deadline). */
export function todayInVietnam(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date())
}

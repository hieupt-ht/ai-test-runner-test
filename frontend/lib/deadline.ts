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

/** Cộng `days` ngày vào ngày YYYY-MM-DD, tính theo lịch (không lệch múi giờ). */
export function addDays(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * MS_PER_DAY).toISOString().slice(0, 10)
}

/** Deadline gợi ý khi nhận module: hạn xa nhất của người đang làm; chưa ai làm hoặc đã quá hạn thì hôm nay + 7 ngày. */
export function defaultModuleDeadline(workerDeadlines: string[], today: string): string {
  const latest = [...workerDeadlines].sort().at(-1)
  return latest && latest >= today ? latest : addDays(today, 7)
}

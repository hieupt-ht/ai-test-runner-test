"use client"

import { useTranslations } from "next-intl"

export type ProgressItem = { id: string; label: string; done: number; total: number }

/** Thanh tiến độ ngang cho từng mục (màn hình hoặc dự án). Không cần Recharts. */
export function ProgressList({ items }: { items: ProgressItem[] }) {
  const t = useTranslations("charts")

  if (items.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">{t("empty")}</p>
  }

  return (
    <ul className="space-y-3">
      {items.map((item) => {
        // total = 0 thì coi như 0%, tránh chia cho 0
        const percent = item.total > 0 ? Math.round((item.done / item.total) * 100) : 0
        return (
          <li key={item.id}>
            <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
              <span className="min-w-0 truncate">{item.label}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {item.done}/{item.total} · {percent}%
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={item.label}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={percent}
              className="h-2 overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

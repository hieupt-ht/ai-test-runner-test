"use client"

import { useTranslations } from "next-intl"
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import type { DayCount } from "@/lib/api/types"

/** "2026-11-19" -> "19/11" */
function shortDay(day: string) {
  const [, month, date] = day.split("-")
  return `${date}/${month}`
}

/** Cột chồng Pass / Fail / Khác theo ngày. Màu lấy từ biến CSS nên đổi theo giao diện. */
export default function PassFailChart({ days }: { days: DayCount[] }) {
  const t = useTranslations("charts")
  const total = days.reduce(
    (sum, item) => ({
      passed: sum.passed + item.passed,
      failed: sum.failed + item.failed,
      other: sum.other + item.other,
    }),
    { passed: 0, failed: 0, other: 0 },
  )
  const isEmpty = total.passed + total.failed + total.other === 0
  const data = days.map((item) => ({ ...item, label: shortDay(item.day) }))

  return (
    <figure aria-label={t("passFailLabel")} className="m-0">
      <figcaption className="sr-only">
        {t("passFailSummary", { days: days.length, ...total })}
      </figcaption>
      {isEmpty ? (
        <p className="py-16 text-center text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <div className="h-56 w-full" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
              <Tooltip
                cursor={{ fill: "var(--muted)" }}
                contentStyle={{
                  background: "var(--popover)",
                  color: "var(--popover-foreground)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              />
              <Bar dataKey="passed" name={t("pass")} stackId="a" fill="var(--chart-pass)" />
              <Bar dataKey="failed" name={t("fail")} stackId="a" fill="var(--chart-fail)" />
              <Bar dataKey="other" name={t("other")} stackId="a" fill="var(--chart-other)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </figure>
  )
}

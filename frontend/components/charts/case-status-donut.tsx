"use client"

import { useTranslations } from "next-intl"
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts"

type StatusKey = "DRAFT" | "IN_REVIEW" | "APPROVED" | "TESTED"

const SLICES: { key: StatusKey; labelKey: string; color: string }[] = [
  { key: "DRAFT", labelKey: "draft", color: "var(--chart-1)" },
  { key: "IN_REVIEW", labelKey: "inReview", color: "var(--chart-2)" },
  { key: "APPROVED", labelKey: "approved", color: "var(--chart-3)" },
  { key: "TESTED", labelKey: "tested", color: "var(--chart-4)" },
]

/** Vòng tròn chia theo trạng thái case. */
export default function CaseStatusDonut({ counts }: { counts: Record<StatusKey, number> }) {
  const t = useTranslations("charts")
  const total = SLICES.reduce((sum, slice) => sum + counts[slice.key], 0)
  const data = SLICES.map((slice) => ({
    name: t(slice.labelKey),
    value: counts[slice.key],
    color: slice.color,
  }))

  return (
    <figure aria-label={t("statusLabel")} className="m-0">
      <figcaption className="sr-only">{t("statusSummary", counts)}</figcaption>
      {total === 0 ? (
        <p className="py-16 text-center text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <>
          <div className="h-44 w-full" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data} dataKey="value" innerRadius="55%" outerRadius="90%" stroke="var(--card)">
                  {data.map((slice) => (
                    <Cell key={slice.name} fill={slice.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--popover)",
                    color: "var(--popover-foreground)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          {/* Chú thích tự vẽ để chữ dùng đúng màu giao diện */}
          <ul className="mt-2 grid grid-cols-2 gap-1 text-xs text-muted-foreground" aria-hidden="true">
            {data.map((slice) => (
              <li key={slice.name} className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-full" style={{ background: slice.color }} />
                {slice.name} · {slice.value}
              </li>
            ))}
          </ul>
        </>
      )}
    </figure>
  )
}

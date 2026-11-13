"use client"

import { useFormatter, useTranslations } from "next-intl"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { AuditEntry } from "@/lib/api/types"

const KNOWN_ACTIONS = ["CREATE", "UPDATE", "SUBMIT", "APPROVE", "RETURN", "DEPRECATE", "RESTORE"]
const KNOWN_FIELDS = [
  "title",
  "precondition",
  "test_data",
  "steps",
  "expected_result",
  "severity",
  "priority",
  "status",
]

/** Nhận xét đi kèm một dòng lịch sử (chỉ có ở RETURN: diff.comment). */
export function commentOf(entry: AuditEntry): string {
  const comment = entry.diff.comment
  return typeof comment === "string" ? comment : ""
}

/** Lần trả lại gần nhất (theo thời gian), hoặc undefined nếu chưa từng bị trả lại. */
export function latestReturn(history: AuditEntry[]): AuditEntry | undefined {
  return history
    .filter((entry) => entry.action === "RETURN")
    .sort((a, b) => b.at.localeCompare(a.at))[0]
}

export function HistoryPanel({ history }: { history: AuditEntry[] }) {
  const t = useTranslations("testCases.history")
  const format = useFormatter()
  // Mới nhất lên đầu.
  const entries = [...history].sort((a, b) => b.at.localeCompare(a.at))

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length === 0 && <p className="text-sm text-muted-foreground">{t("empty")}</p>}
        <ol className="flex flex-col gap-3">
          {entries.map((entry, index) => {
            const comment = commentOf(entry)
            const fields = Object.keys(entry.diff).filter((key) => KNOWN_FIELDS.includes(key))
            return (
              <li key={`${entry.at}-${index}`} className="border-l-2 pl-3 text-sm">
                <p className="font-medium">
                  {KNOWN_ACTIONS.includes(entry.action) ? t(`action.${entry.action}`) : entry.action}
                </p>
                <p className="text-xs text-muted-foreground">
                  {entry.actor} ·{" "}
                  {format.dateTime(new Date(entry.at), { dateStyle: "medium", timeStyle: "short" })}
                </p>
                {entry.action === "UPDATE" && fields.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {t("fields", { fields: fields.map((field) => t(`field.${field}`)).join(", ") })}
                  </p>
                )}
                {comment && <p className="mt-1 whitespace-pre-wrap">{t("comment", { comment })}</p>}
              </li>
            )
          })}
        </ol>
      </CardContent>
    </Card>
  )
}

"use client"

import { useTranslations } from "next-intl"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { AuditEntry } from "@/lib/api/types"
import { changedLabels, formatVietnamTime, versionOfEntry } from "@/lib/test-cases/history"

const KNOWN_ACTIONS = ["CREATE", "UPDATE", "SUBMIT", "APPROVE", "RETURN", "DEPRECATE", "RESTORE", "AUTO_APPROVE"]

/** Nhận xét đi kèm một dòng lịch sử (chỉ có ở RETURN: diff.comment). */
export function commentOf(entry: AuditEntry): string {
  const comment = entry.diff.comment
  return typeof comment === "string" ? comment : ""
}

export function HistoryPanel({ history }: { history: AuditEntry[] }) {
  const t = useTranslations("testCases.history")
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
            const fields = changedLabels(entry.diff)
            return (
              <li key={`${entry.at}-${index}`} className="border-l-2 pl-3 text-sm">
                <p className="font-medium">
                  {KNOWN_ACTIONS.includes(entry.action) ? t(`action.${entry.action}`) : entry.action}
                </p>
                <p className="text-xs text-muted-foreground">
                  {`v${versionOfEntry(index, entries.length)} · ${formatVietnamTime(entry.at)} · ${entry.actor}`}
                </p>
                {entry.action === "UPDATE" && fields.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {t("fields", { fields: fields.join(", ") })}
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

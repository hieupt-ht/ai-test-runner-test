"use client"

import { useTranslations } from "next-intl"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { Board, LeaderboardRow } from "@/lib/api/types"

const MEDALS: Record<number, string> = { 1: "🥇", 2: "🥈", 3: "🥉" }

function Row({ row, isMe }: { row: LeaderboardRow; isMe: boolean }) {
  const t = useTranslations("leaderboard")
  return (
    <li className={`flex items-center gap-3 text-sm ${isMe ? "font-semibold text-primary" : ""}`}>
      <span className="w-8 shrink-0 text-center tabular-nums">
        {row.rank === null ? "–" : (MEDALS[row.rank] ?? row.rank)}
      </span>
      <span className="min-w-0 flex-1 truncate">{row.name}</span>
      {isMe && <span className="shrink-0 text-xs">{t("you")}</span>}
      <span className="shrink-0 tabular-nums">{row.rank === null ? t("noScore") : row.count}</span>
    </li>
  )
}

/** Một bảng xếp hạng: top 5, dòng của mình in đậm; ngoài top thì hiện thêm dưới dấu "…". */
export function LeaderboardCard({
  title,
  board,
  meEmail,
}: {
  title: string
  board: Board
  meEmail: string
}) {
  const t = useTranslations("leaderboard")
  const top = board.top.slice(0, 5)
  const meInTop = top.some((row) => row.email === meEmail)
  const showMeBelow = board.me !== null && !meInTop

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {top.length === 0 && !showMeBelow ? (
          <p className="text-sm text-muted-foreground">{t("empty")}</p>
        ) : (
          <ol className="space-y-2">
            {top.map((row) => (
              <Row key={row.email} row={row} isMe={row.email === meEmail} />
            ))}
            {showMeBelow && board.me && (
              <>
                <li aria-hidden="true" className="text-center text-muted-foreground">
                  …
                </li>
                <Row row={board.me} isMe />
              </>
            )}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}

"use client"

import { useTranslations } from "next-intl"

import { Hedgehog } from "@/components/pet/hedgehog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useMyPet } from "@/lib/use-stats"

/** Thẻ "Nhím của tôi": con nhím, cấp, chuỗi ngày và tiến độ lên cấp. */
export function PetCard() {
  const t = useTranslations("pet")
  const { data: pet } = useMyPet()

  if (!pet) {
    return (
      <Card>
        <CardContent className="flex items-center gap-4 py-6">
          <Skeleton className="h-28 w-32" />
          <Skeleton className="h-16 flex-1" />
        </CardContent>
      </Card>
    )
  }

  // Cấp tối đa 4; API luôn trả 1–4
  const level = Math.min(Math.max(pet.level, 1), 4) as 1 | 2 | 3 | 4
  // Thanh tiến độ: số bug đã bắt trên tổng số bug cần để lên cấp kế
  const percent =
    pet.bugs_to_next === null ? 100 : Math.round((pet.bugs / (pet.bugs + pet.bugs_to_next)) * 100)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-4 sm:flex-row">
        <div className="flex w-full shrink-0 justify-center sm:w-52">
          <Hedgehog level={level} mood={pet.mood} />
        </div>
        <div className="w-full min-w-0 space-y-2">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <p className="text-xl font-semibold">{t(`level.${level}`)}</p>
            <p className="text-sm font-medium tabular-nums">
              <span className="sr-only">{t("streakLabel")}: </span>
              {t("streak", { count: pet.streak })}
            </p>
            <p className="text-sm tabular-nums text-muted-foreground">{t("bugs", { count: pet.bugs })}</p>
          </div>
          <p className="text-sm text-muted-foreground">{t(`moodText.${pet.mood}`)}</p>
          {pet.bugs_to_next === null ? (
            <p className="text-sm font-medium">{t("maxLevel")}</p>
          ) : (
            <div>
              <p className="mb-1 text-sm">{t("toNext", { count: pet.bugs_to_next })}</p>
              <div
                role="progressbar"
                aria-label={t("toNext", { count: pet.bugs_to_next })}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percent}
                className="h-2 overflow-hidden rounded-full bg-muted"
              >
                <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

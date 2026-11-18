"use client"

import { useTranslations } from "next-intl"

import { Input } from "@/components/ui/input"
import type { Platform } from "@/lib/api/types"

export type ResultFilterValues = {
  platform: Platform | undefined
  runId: string | undefined
  regressionOnly: boolean
}

const PLATFORMS: Platform[] = ["WEB", "ANDROID", "IOS"]

type Props = {
  value: ResultFilterValues
  onChange: (next: ResultFilterValues) => void
}

/** Ba bộ lọc của trang Kết quả: nền tảng, mã Run và chỉ regression. */
export function ResultFilters({ value, onChange }: Props) {
  const t = useTranslations("results")
  const tp = useTranslations("testCases")
  return (
    <div className="flex flex-wrap items-end gap-3 text-sm">
      <label className="flex flex-col gap-1">
        <span>{t("filters.platform")}</span>
        <select
          aria-label={t("filters.platform")}
          value={value.platform ?? ""}
          onChange={(event) =>
            onChange({ ...value, platform: (event.target.value || undefined) as Platform | undefined })
          }
          className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm"
        >
          <option value="">{t("filters.allPlatforms")}</option>
          {PLATFORMS.map((platform) => (
            <option key={platform} value={platform}>
              {tp(`platform.${platform}`)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span>{t("filters.run")}</span>
        <Input
          aria-label={t("filters.run")}
          placeholder={t("filters.runPlaceholder")}
          value={value.runId ?? ""}
          onChange={(event) => onChange({ ...value, runId: event.target.value.trim() || undefined })}
          className="w-36"
        />
      </label>
      <label className="flex h-8 items-center gap-2">
        <input
          type="checkbox"
          className="size-4"
          checked={value.regressionOnly}
          onChange={(event) => onChange({ ...value, regressionOnly: event.target.checked })}
        />
        <span>{t("filters.regressionOnly")}</span>
      </label>
    </div>
  )
}

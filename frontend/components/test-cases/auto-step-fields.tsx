"use client"

import { useTranslations } from "next-intl"

import { Input } from "@/components/ui/input"
import type { AutoStep, AutoType, TargetBy } from "@/lib/api/types"
import { AUTO_TYPES, autoHasValueField, autoNeedsTarget, defaultAuto } from "@/lib/test-cases/steps"

type Props = {
  /** Số thứ tự bước (bắt đầu từ 1), dùng cho nhãn đọc màn hình. */
  stepNumber: number
  value: AutoStep | undefined
  onChange: (next: AutoStep | undefined) => void
  disabled?: boolean
  /** Khoá lỗi trong testCases.form.errors, nếu có. */
  error?: string
}

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30"

/** Phần "Tự động" của một bước: thu gọn mặc định, mở ra để chọn hành động cho worker chạy. */
export function AutoStepFields({ stepNumber, value, onChange, disabled, error }: Props) {
  const t = useTranslations("testCases")
  const label = (key: string) => `${t(key)} ${stepNumber}`
  const target = value?.target

  function changeType(next: string) {
    onChange(next === "" ? undefined : defaultAuto(next as AutoType))
  }

  function changeTarget(patch: { by?: TargetBy; value?: string }) {
    if (!value || !target) return
    onChange({ ...value, target: { ...target, ...patch } })
  }

  /** Gõ CSS thì chuyển sang tìm bằng CSS; xoá hết thì quay về cách tìm mặc định của loại bước. */
  function changeCss(css: string) {
    if (!value || !target) return
    if (css !== "") {
      onChange({ ...value, target: { by: "css", value: css } })
      return
    }
    const fallback = value.type === "click" ? "text" : "label"
    onChange({ ...value, target: { by: fallback, value: "" } })
  }

  return (
    <details open={Boolean(error) || undefined} className="rounded-lg border bg-muted/30 px-2 py-1">
      <summary className="cursor-pointer select-none text-xs font-medium text-muted-foreground">
        {t("auto.title")}
        {value && <span className="ml-2 font-normal">· {t(`auto.types.${value.type}`)}</span>}
      </summary>

      <div className="mt-2 flex flex-col gap-2 pb-1">
        <p className="text-xs text-muted-foreground">{t("auto.hint")}</p>

        <select
          aria-label={label("auto.type")}
          className={`${selectClass} w-full sm:w-64`}
          value={value?.type ?? ""}
          disabled={disabled}
          onChange={(event) => changeType(event.target.value)}
        >
          <option value="">{t("auto.none")}</option>
          {AUTO_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(`auto.types.${type}`)}
            </option>
          ))}
        </select>

        {value && autoNeedsTarget(value.type) && target && target.by !== "css" && (
          <div className="flex flex-col gap-2 sm:flex-row">
            <select
              aria-label={label("auto.by")}
              className={`${selectClass} w-full sm:w-40`}
              value={target.by}
              disabled={disabled}
              onChange={(event) => changeTarget({ by: event.target.value as TargetBy })}
            >
              <option value="text">{t("auto.byText")}</option>
              <option value="label">{t("auto.byLabel")}</option>
            </select>
            <Input
              aria-label={label("auto.target")}
              placeholder={t("auto.targetPlaceholder")}
              value={target.value}
              disabled={disabled}
              onChange={(event) => changeTarget({ value: event.target.value })}
            />
          </div>
        )}

        {value && autoHasValueField(value.type) && (
          <Input
            aria-label={label("auto.value")}
            placeholder={t(`auto.valuePlaceholders.${value.type}`)}
            value={value.value}
            disabled={disabled}
            onChange={(event) => onChange({ ...value, value: event.target.value })}
          />
        )}

        {value && autoNeedsTarget(value.type) && target && (
          <details open={target.by === "css" || undefined}>
            <summary className="cursor-pointer select-none text-xs text-muted-foreground">
              {t("auto.advanced")}
            </summary>
            <div className="mt-1 flex flex-col gap-1">
              <Input
                aria-label={label("auto.css")}
                placeholder={t("auto.cssPlaceholder")}
                value={target.by === "css" ? target.value : ""}
                disabled={disabled}
                onChange={(event) => changeCss(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">{t("auto.cssHint")}</p>
            </div>
          </details>
        )}

        {error && <p className="text-xs text-destructive">{t(`form.errors.${error}`)}</p>}
      </div>
    </details>
  )
}

"use client"

import { ArrowDown, ArrowUp, GripVertical, Plus, Trash2 } from "lucide-react"
import { useTranslations } from "next-intl"
import { useEffect, useRef, useState } from "react"

import { MediaPicker } from "@/components/media/media-picker"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { TestStep } from "@/lib/api/types"
import { LIMITS } from "@/lib/test-cases/form-schema"
import { insertStepAfter, moveStep, removeStep } from "@/lib/test-cases/steps"

type Props = {
  steps: TestStep[]
  onChange: (steps: TestStep[]) => void
  /** Mã lỗi (khoá trong testCases.form.errors) theo từng bước, nếu có */
  errors?: ({ action?: string; expected?: string } | undefined)[]
  disabled?: boolean
  /** Cần để xin chữ ký tải ảnh/video lên */
  projectId: string
  /** Nơi lưu ảnh/video của dự án */
  storage?: "cloudinary" | "drive"
  /** Báo form biết bước nào đang tải ảnh/video (khoá nút Lưu/Gửi) */
  onBusyChange?: (key: string, busy: boolean) => void
}

/** Trình soạn các bước: kéo thả (HTML5), nút lên/xuống, xoá, Ctrl+Enter để thêm bước dưới. */
export function StepsEditor({
  steps,
  onChange,
  errors = [],
  disabled,
  projectId,
  storage,
  onBusyChange,
}: Props) {
  const t = useTranslations("testCases")
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)
  const actionRefs = useRef<(HTMLTextAreaElement | null)[]>([])
  // Sau khi thêm bước bằng Ctrl+Enter, đưa con trỏ vào ô của bước mới ở lần vẽ kế tiếp.
  const pendingFocus = useRef<number | null>(null)

  useEffect(() => {
    if (pendingFocus.current === null) return
    actionRefs.current[pendingFocus.current]?.focus()
    pendingFocus.current = null
  })

  function update(index: number, patch: Partial<TestStep>) {
    onChange(steps.map((step, i) => (i === index ? { ...step, ...patch } : step)))
  }

  function addAfter(index: number) {
    if (steps.length >= LIMITS.steps) return
    onChange(insertStepAfter(steps, index))
    pendingFocus.current = index + 1
  }

  function endDrag() {
    setDragIndex(null)
    setOverIndex(null)
  }

  function drop(to: number) {
    if (dragIndex !== null) onChange(moveStep(steps, dragIndex, to))
    endDrag()
  }

  return (
    <div className="flex flex-col gap-2">
      {steps.map((step, index) => {
        const error = errors[index]
        return (
          <div
            key={index}
            onDragOver={(event) => {
              if (dragIndex === null) return
              event.preventDefault() // bắt buộc để ô này nhận được sự kiện drop
              setOverIndex(index)
            }}
            onDrop={(event) => {
              event.preventDefault()
              drop(index)
            }}
            className={`flex gap-2 rounded-lg border p-2 ${
              overIndex === index && dragIndex !== index ? "border-primary" : ""
            } ${dragIndex === index ? "opacity-50" : ""}`}
          >
            <div className="flex flex-col items-center gap-1 pt-1">
              <span
                draggable={!disabled}
                onDragStart={(event) => {
                  // Firefox không bắt đầu kéo nếu chưa có dữ liệu kéo
                  event.dataTransfer.setData("text/plain", String(index))
                  event.dataTransfer.effectAllowed = "move"
                  setDragIndex(index)
                }}
                onDragEnd={endDrag}
                title={t("steps.drag")}
                className="cursor-grab text-muted-foreground"
              >
                <GripVertical className="size-4" />
              </span>
              <span className="font-mono text-xs text-muted-foreground">{index + 1}</span>
            </div>

            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <Textarea
                ref={(element) => {
                  actionRefs.current[index] = element
                }}
                rows={2}
                value={step.action}
                disabled={disabled}
                placeholder={t("steps.action")}
                aria-label={`${t("steps.action")} ${index + 1}`}
                aria-invalid={Boolean(error?.action)}
                onChange={(event) => update(index, { action: event.target.value })}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault()
                    addAfter(index)
                  }
                }}
              />
              {error?.action && (
                <p className="text-xs text-destructive">{t(`form.errors.${error.action}`)}</p>
              )}
              <Input
                value={step.expected}
                disabled={disabled}
                placeholder={t("steps.expected")}
                aria-label={`${t("steps.expected")} ${index + 1}`}
                aria-invalid={Boolean(error?.expected)}
                onChange={(event) => update(index, { expected: event.target.value })}
              />
              {error?.expected && (
                <p className="text-xs text-destructive">{t(`form.errors.${error.expected}`)}</p>
              )}
              <MediaPicker
                value={step.guide_media ?? []}
                onChange={(guide_media) => update(index, { guide_media })}
                projectId={projectId}
                storage={storage}
                disabled={disabled}
                onBusyChange={(busy) => onBusyChange?.(`step-${index}`, busy)}
              />
            </div>

            {!disabled && (
              <div className="flex flex-col gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={t("steps.moveUp")}
                  disabled={index === 0}
                  onClick={() => onChange(moveStep(steps, index, index - 1))}
                >
                  <ArrowUp />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={t("steps.moveDown")}
                  disabled={index === steps.length - 1}
                  onClick={() => onChange(moveStep(steps, index, index + 1))}
                >
                  <ArrowDown />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={t("steps.remove")}
                  disabled={steps.length <= 1}
                  onClick={() => onChange(removeStep(steps, index))}
                >
                  <Trash2 />
                </Button>
              </div>
            )}
          </div>
        )
      })}

      {!disabled && (
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={steps.length >= LIMITS.steps}
            onClick={() => addAfter(steps.length - 1)}
          >
            <Plus /> {t("steps.add")}
          </Button>
          <span className="text-xs text-muted-foreground">{t("steps.hint")}</span>
        </div>
      )}
    </div>
  )
}

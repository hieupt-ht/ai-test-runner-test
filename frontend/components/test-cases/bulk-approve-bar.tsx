"use client"

import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { ApproveItem } from "@/lib/use-test-cases"
import { useApproveTestCases } from "@/lib/use-test-cases"
import { batchSummary } from "@/lib/test-cases/selection"

type Props = {
  projectId: string
  items: ApproveItem[]
  /** Gọi sau khi duyệt xong (kể cả khi có case bị bỏ qua) để trang bỏ chọn */
  onDone: () => void
  onClear: () => void
  /** Dự án tắt bước duyệt: nút duyệt hàng loạt mờ đi */
  reviewDisabled?: boolean
}

/** Thanh hiện khi có case được chọn: "Duyệt N case" kèm hộp xác nhận. */
export function BulkApproveBar({ projectId, items, onDone, onClear, reviewDisabled }: Props) {
  const t = useTranslations("testCases.bulk")
  const tCommon = useTranslations("common")
  const tCases = useTranslations("testCases")
  const approve = useApproveTestCases(projectId)
  const [open, setOpen] = useState(false)

  if (items.length === 0) return null

  async function confirm() {
    try {
      const result = await approve.mutateAsync(items)
      const { approved, skipped } = batchSummary(result)
      setOpen(false)
      if (skipped === 0) {
        toast.success(t("approvedAll", { approved }))
      } else {
        const details = result.skipped
          .map((item) => t("skippedItem", { id: item.case_id, reason: item.reason }))
          .join("\n")
        toast.warning(t("result", { approved, skipped }), { description: details })
      }
      onDone()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-sm">
      <span>{t("selected", { count: items.length })}</span>
      <Button
        size="sm"
        disabled={reviewDisabled}
        title={reviewDisabled ? tCases("reviewOff") : undefined}
        onClick={() => setOpen(true)}
      >
        {t("approve", { count: items.length })}
      </Button>
      <Button size="sm" variant="ghost" onClick={onClear}>
        {t("clear")}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("confirmTitle", { count: items.length })}</DialogTitle>
            <DialogDescription>{t("confirmDescription")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>{tCommon("cancel")}</DialogClose>
            <Button disabled={approve.isPending} onClick={() => void confirm()}>
              {t("approve", { count: items.length })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

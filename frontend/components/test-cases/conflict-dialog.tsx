"use client"

import { useTranslations } from "next-intl"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

type Props = {
  /** Câu báo xung đột từ backend; null thì hộp thoại đóng */
  message: string | null
  onReload: () => void
  onClose: () => void
}

/** Báo "case vừa bị người khác sửa". Không so sánh hay gộp: chỉ cho tải lại bản mới nhất. */
export function ConflictDialog({ message, onReload, onClose }: Props) {
  const t = useTranslations("testCases.conflict")
  return (
    <Dialog open={message !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{message}</DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">{t("hint")}</p>
        <DialogFooter>
          <Button onClick={onReload}>{t("reload")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

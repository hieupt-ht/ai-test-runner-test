"use client"

import { useTranslations } from "next-intl"
import type { ReactElement } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

type Props = {
  /** Nút mở hộp thoại, ví dụ <Button variant="ghost" /> */
  trigger: ReactElement
  triggerLabel: React.ReactNode
  title: string
  description: string
  onConfirm: () => void
}

/** Hỏi lại trước thao tác không hoàn tác được (xoá, bỏ thành viên...). */
export function ConfirmDialog({ trigger, triggerLabel, title, description, onConfirm }: Props) {
  const t = useTranslations("common")
  return (
    <Dialog>
      <DialogTrigger render={trigger}>{triggerLabel}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>{t("cancel")}</DialogClose>
          <DialogClose render={<Button variant="destructive" />} onClick={onConfirm}>
            {t("confirm")}
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

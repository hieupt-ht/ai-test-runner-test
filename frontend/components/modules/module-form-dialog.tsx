"use client"

import { useTranslations } from "next-intl"
import { useState, type ReactElement } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { Module } from "@/lib/api/types"
import { useSaveModule } from "@/lib/use-modules"

type Props = {
  projectId: string
  /** Có thì là sửa, không có thì là thêm mới */
  module?: Module
  trigger: ReactElement
  triggerLabel: React.ReactNode
  /** Gọi sau khi lưu xong, kèm module vừa lưu */
  onSaved?: (module: Module) => void
}

export function ModuleFormDialog({ projectId, module, trigger, triggerLabel, onSaved }: Props) {
  const t = useTranslations("modules")
  const tCommon = useTranslations("common")
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(module?.name ?? "")
  const [description, setDescription] = useState(module?.description ?? "")
  const [submitted, setSubmitted] = useState(false)
  const save = useSaveModule(projectId)

  // Mỗi lần mở lại thì nạp lại từ dữ liệu đã lưu
  function handleOpenChange(next: boolean) {
    if (next && module) {
      setName(module.name)
      setDescription(module.description)
      setSubmitted(false)
    }
    setOpen(next)
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (!name.trim()) return
    try {
      const saved = await save.mutateAsync({
        id: module?.id,
        name: name.trim(),
        description: description.trim(),
      })
      toast.success(tCommon("saved"))
      onSaved?.(saved)
      setOpen(false)
      if (!module) {
        setName("")
        setDescription("")
        setSubmitted(false)
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger}>{triggerLabel}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {module ? t("formEdit", { id: module.id }) : t("formAdd")}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="module-name">{t("fieldName")}</Label>
            <Input id="module-name" value={name} onChange={(e) => setName(e.target.value)} />
            {submitted && !name.trim() && (
              <p className="text-xs text-destructive">{t("nameRequired")}</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="module-description">{t("fieldDescription")}</Label>
            <textarea
              id="module-description"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
            />
          </div>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>
              {tCommon("cancel")}
            </DialogClose>
            <Button type="submit" disabled={save.isPending}>
              {tCommon("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

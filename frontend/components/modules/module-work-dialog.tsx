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
import type { MemberView, ModuleView } from "@/lib/api/types"
import { defaultModuleDeadline, todayInVietnam } from "@/lib/deadline"
import { useAssignModule } from "@/lib/use-modules"

type Props = {
  projectId: string
  module: ModuleView
  /** assign: QA chọn tester để giao; claim: tester tự nhận cho mình */
  mode: "assign" | "claim"
  /** Tester đang hoạt động trong dự án (dùng ở chế độ assign) */
  testers: MemberView[]
  meEmail: string
  trigger: ReactElement
  triggerLabel: React.ReactNode
}

/** Giao / nhận module. Module đã có người làm chỉ hiện cảnh báo đỏ, không chặn. */
export function ModuleWorkDialog({
  projectId,
  module,
  mode,
  testers,
  meEmail,
  trigger,
  triggerLabel,
}: Props) {
  const t = useTranslations("modules")
  const tCommon = useTranslations("common")
  const today = todayInVietnam()
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const defaultDeadline = () =>
    defaultModuleDeadline(
      module.workers.map((worker) => worker.deadline),
      today,
    )
  const [deadline, setDeadline] = useState(defaultDeadline)
  const [submitted, setSubmitted] = useState(false)
  const assign = useAssignModule(projectId)

  const others = module.workers.filter((worker) => worker.email !== meEmail)
  const emails = mode === "claim" ? [meEmail] : selected

  function toggle(email: string) {
    setSelected((list) =>
      list.includes(email) ? list.filter((item) => item !== email) : [...list, email],
    )
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (emails.length === 0 || !deadline) return
    try {
      await assign.mutateAsync({ moduleId: module.id, emails, deadline })
      toast.success(mode === "claim" ? t("claimed") : t("assigned"))
      setSelected([])
      setSubmitted(false)
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        // Mỗi lần mở tính lại hạn mặc định, vì danh sách người làm có thể đã đổi từ lúc hiện trang
        if (next) setDeadline(defaultDeadline())
        setOpen(next)
      }}
    >
      <DialogTrigger render={trigger}>{triggerLabel}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {mode === "claim"
              ? t("claimTitle", { name: module.name })
              : t("assignTitle", { name: module.name })}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {others.length > 0 && (
            <p className="text-sm font-medium text-destructive">
              {t("warnWorking", { names: others.map((worker) => worker.name).join(", ") })}
            </p>
          )}

          {mode === "assign" && (
            <fieldset className="flex flex-col gap-1.5">
              <legend className="text-sm font-medium">{t("fieldTesters")}</legend>
              {testers.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("noTesters")}</p>
              ) : (
                <div className="flex max-h-56 flex-col gap-1 overflow-y-auto rounded-lg border p-2">
                  {testers.map((tester) => (
                    <label
                      key={tester.email}
                      className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                    >
                      <input
                        type="checkbox"
                        className="size-4 accent-primary"
                        checked={selected.includes(tester.email)}
                        onChange={() => toggle(tester.email)}
                      />
                      <span className="font-medium">{tester.name}</span>
                      <span className="truncate text-xs text-muted-foreground">{tester.email}</span>
                    </label>
                  ))}
                </div>
              )}
              {submitted && selected.length === 0 && (
                <p className="text-xs text-destructive">{t("pickTester")}</p>
              )}
            </fieldset>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="module-deadline">{t("fieldDeadline")}</Label>
            <Input
              id="module-deadline"
              type="date"
              min={today}
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
            {submitted && !deadline && (
              <p className="text-xs text-destructive">{t("pickDeadline")}</p>
            )}
          </div>

          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>{tCommon("cancel")}</DialogClose>
            <Button type="submit" disabled={assign.isPending}>
              {mode === "claim" ? t("claimSubmit") : t("assignSubmit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

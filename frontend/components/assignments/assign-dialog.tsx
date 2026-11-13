"use client"

import { UserPlus } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"
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
import type { MemberView, Screen } from "@/lib/api/types"
import { todayInVietnam } from "@/lib/deadline"
import { useAssign } from "@/lib/use-project-data"

type Props = {
  projectId: string
  screen: Screen
  /** Tester đang hoạt động trong dự án, chưa được giao màn hình này */
  availableTesters: MemberView[]
}

export function AssignDialog({ projectId, screen, availableTesters }: Props) {
  const t = useTranslations()
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [deadline, setDeadline] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const assign = useAssign(projectId)
  const today = todayInVietnam()

  function toggle(email: string) {
    setSelected((emails) =>
      emails.includes(email) ? emails.filter((item) => item !== email) : [...emails, email],
    )
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (selected.length === 0 || !deadline) return
    try {
      await assign.mutateAsync({ screen_id: screen.id, assignee_emails: selected, deadline })
      toast.success(t("assignments.assigned"))
      setSelected([])
      setDeadline("")
      setSubmitted(false)
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" variant="outline" />}>
        <UserPlus /> {t("assignments.assign")}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("assignments.formTitle", { screen: screen.name })}</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <fieldset className="flex flex-col gap-1.5">
            <legend className="text-sm font-medium">{t("assignments.fieldTesters")}</legend>
            {availableTesters.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("assignments.noTesters")}</p>
            ) : (
              <div className="flex max-h-56 flex-col gap-1 overflow-y-auto rounded-lg border p-2">
                {availableTesters.map((tester) => (
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
              <p className="text-xs text-destructive">{t("assignments.pickTester")}</p>
            )}
          </fieldset>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="assign-deadline">{t("assignments.fieldDeadline")}</Label>
            <Input
              id="assign-deadline"
              type="date"
              min={today}
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
            {submitted && !deadline && (
              <p className="text-xs text-destructive">{t("assignments.pickDeadline")}</p>
            )}
          </div>

          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>
              {t("common.cancel")}
            </DialogClose>
            <Button type="submit" disabled={assign.isPending || availableTesters.length === 0}>
              {t("assignments.assign")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useUsers } from "@/components/users/use-users"
import { useAddMember } from "@/lib/use-project-data"

type Props = {
  projectId: string
  /** Admin xem được danh sách user nên được chọn; QA Lead thì gõ email */
  isAdmin: boolean
  memberEmails: string[]
}

export function AddMemberDialog({ projectId, isAdmin, memberEmails }: Props) {
  const t = useTranslations()
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState<string | null>(null)
  const addMember = useAddMember(projectId)
  const users = useUsers({ enabled: isAdmin && open })

  const candidates = (users.data ?? [])
    .filter((user) => user.active && !memberEmails.includes(user.email))
    .map((user) => ({ value: user.email, label: `${user.name} (${user.email})` }))

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const chosen = email?.trim()
    if (!chosen) return
    try {
      const member = await addMember.mutateAsync(chosen)
      toast.success(t("members.added", { email: member.email }))
      setEmail(null)
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <UserPlus /> {t("members.add")}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("members.formTitle")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {isAdmin ? (
            <div className="flex flex-col gap-1.5">
              <Label>{t("members.fieldUser")}</Label>
              <Select items={candidates} value={email} onValueChange={setEmail}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t("members.pickUser")} />
                </SelectTrigger>
                <SelectContent>
                  {candidates.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="member-email">{t("members.fieldEmail")}</Label>
              <Input
                id="member-email"
                type="email"
                placeholder="ten@congty.com"
                value={email ?? ""}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          )}
          <DialogFooter>
            <DialogClose render={<Button variant="outline" type="button" />}>
              {t("common.cancel")}
            </DialogClose>
            <Button type="submit" disabled={!email?.trim() || addMember.isPending}>
              {t("members.add")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

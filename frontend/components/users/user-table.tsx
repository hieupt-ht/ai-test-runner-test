"use client"

import { KeyRound } from "lucide-react"
import { useFormatter, useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ResetPasswordDialog } from "@/components/users/reset-password-dialog"
import { RoleSelect } from "@/components/users/role-select"
import { useUpdateUser } from "@/components/users/use-users"
import type { Role, User } from "@/lib/api/types"

type Props = { users: User[]; currentUserEmail: string }

export function UserTable({ users, currentUserEmail }: Props) {
  const t = useTranslations("users")
  const format = useFormatter()
  const updateUser = useUpdateUser()
  const [resetEmail, setResetEmail] = useState<string | null>(null)

  async function saveChange(user: User, changes: { active?: boolean; role?: Role }) {
    try {
      await updateUser.mutateAsync({ email: user.email, ...changes })
      toast.success(t("updated", { email: user.email }))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("colEmail")}</TableHead>
            <TableHead>{t("colName")}</TableHead>
            <TableHead>{t("colRole")}</TableHead>
            <TableHead>{t("colActive")}</TableHead>
            <TableHead className="text-right">{t("colCreatedAt")}</TableHead>
            <TableHead className="w-12">
              <span className="sr-only">{t("colActions")}</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                {t("empty")}
              </TableCell>
            </TableRow>
          )}
          {users.map((user) => {
            const isSelf = user.email === currentUserEmail
            return (
              <TableRow key={user.email}>
                <TableCell className="font-medium">
                  {user.email}
                  {isSelf && (
                    <Badge variant="secondary" className="ml-2">
                      {t("you")}
                    </Badge>
                  )}
                </TableCell>
                <TableCell>{user.name}</TableCell>
                <TableCell>
                  {/* Admin không tự đổi vai trò của mình, để hệ thống không mất Admin */}
                  <RoleSelect
                    value={user.role}
                    disabled={isSelf || updateUser.isPending}
                    onChange={(role) => saveChange(user, { role })}
                    label={t("roleOf", { email: user.email })}
                  />
                </TableCell>
                <TableCell>
                  <Switch
                    checked={user.active}
                    disabled={isSelf || updateUser.isPending}
                    onCheckedChange={(checked) => saveChange(user, { active: checked })}
                    aria-label={t("colActive")}
                  />
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {format.dateTime(new Date(user.created_at), { dateStyle: "medium" })}
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={t("resetFor", { email: user.email })}
                    title={t("resetTitle")}
                    onClick={() => setResetEmail(user.email)}
                  >
                    <KeyRound />
                  </Button>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      {resetEmail && (
        <ResetPasswordDialog
          email={resetEmail}
          open
          onOpenChange={(open) => !open && setResetEmail(null)}
        />
      )}
    </div>
  )
}

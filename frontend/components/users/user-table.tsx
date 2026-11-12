"use client"

import { useFormatter, useTranslations } from "next-intl"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { RoleBadge } from "@/components/users/role-badge"
import { useUpdateUser } from "@/components/users/use-users"
import type { User } from "@/lib/api/types"

type Props = { users: User[]; currentUserEmail: string }

export function UserTable({ users, currentUserEmail }: Props) {
  const t = useTranslations("users")
  const format = useFormatter()
  const updateUser = useUpdateUser()

  async function toggleActive(user: User, active: boolean) {
    try {
      await updateUser.mutateAsync({ email: user.email, active })
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
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
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
                  <RoleBadge role={user.role} />
                </TableCell>
                <TableCell>
                  <Switch
                    checked={user.active}
                    disabled={isSelf || updateUser.isPending}
                    onCheckedChange={(checked) => toggleActive(user, checked)}
                    aria-label={t("colActive")}
                  />
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {format.dateTime(new Date(user.created_at), { dateStyle: "medium" })}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

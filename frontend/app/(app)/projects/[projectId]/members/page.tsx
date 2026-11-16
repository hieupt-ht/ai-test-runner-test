"use client"

import { UserMinus } from "lucide-react"
import { useFormatter, useTranslations } from "next-intl"
import { toast } from "sonner"

import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { AddMemberDialog } from "@/components/members/add-member-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useMe } from "@/lib/use-me"
import { useMembers, useRemoveMember } from "@/lib/use-project-data"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"

export default function MembersPage() {
  const t = useTranslations()
  const format = useFormatter()
  const projectId = useProjectId()
  const { user } = useMe()
  const { data: project } = useProject(projectId)
  const membersQuery = useMembers(projectId)
  const removeMember = useRemoveMember(projectId)

  const canManage = Boolean(project?.permissions.includes("MANAGE_MEMBERS")) && !project?.archived
  const members = membersQuery.data ?? []

  async function remove(email: string) {
    try {
      await removeMember.mutateAsync(email)
      toast.success(t("members.removed", { email }))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  if (membersQuery.isLoading) return <Skeleton className="h-48 w-full" />

  return (
    <div className="flex flex-col gap-4">
      {canManage && (
        <div className="flex justify-end">
          <AddMemberDialog
            projectId={projectId}
            isAdmin={user?.role === "ADMIN"}
            memberEmails={members.map((member) => member.email)}
          />
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("members.colName")}</TableHead>
              <TableHead>{t("members.colEmail")}</TableHead>
              <TableHead>{t("members.colRole")}</TableHead>
              <TableHead>{t("members.colAddedAt")}</TableHead>
              {canManage && <TableHead className="w-16" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  {t("members.empty")}
                </TableCell>
              </TableRow>
            )}
            {members.map((member) => (
              <TableRow key={member.email}>
                <TableCell className="font-medium">
                  {member.name}
                  {!member.active && (
                    <Badge variant="secondary" className="ml-2">
                      {t("members.inactive")}
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">{member.email}</TableCell>
                <TableCell>{t(`roles.${member.role}`)}</TableCell>
                <TableCell className="text-muted-foreground">
                  {format.dateTime(new Date(member.added_at), { dateStyle: "medium" })}
                </TableCell>
                {canManage && (
                  <TableCell>
                    <ConfirmDialog
                      trigger={
                        <Button variant="ghost" size="icon" aria-label={t("members.remove")} />
                      }
                      triggerLabel={<UserMinus />}
                      title={t("members.removeTitle", { email: member.email })}
                      description={t("members.removeConfirm")}
                      onConfirm={() => remove(member.email)}
                    />
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

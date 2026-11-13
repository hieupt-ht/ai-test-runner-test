"use client"

import { X } from "lucide-react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { AssignDialog } from "@/components/assignments/assign-dialog"
import { DeadlineBadge, StatusBadge } from "@/components/common/badges"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAssignments, useMembers, useScreens, useUnassign } from "@/lib/use-project-data"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"

export default function AssignmentsPage() {
  const t = useTranslations()
  const projectId = useProjectId()
  const { data: project } = useProject(projectId)
  const screens = useScreens(projectId)
  const assignments = useAssignments(projectId)
  const members = useMembers(projectId)
  const unassign = useUnassign(projectId)

  const canManage = Boolean(project?.permissions.includes("MANAGE_SCREENS")) && !project?.archived

  if (screens.isLoading || assignments.isLoading || members.isLoading) {
    return <Skeleton className="h-48 w-full" />
  }

  const memberByEmail = new Map((members.data ?? []).map((member) => [member.email, member]))
  const activeTesters = (members.data ?? []).filter((m) => m.role === "TESTER" && m.active)

  async function remove(assignmentId: string) {
    try {
      await unassign.mutateAsync(assignmentId)
      toast.success(t("assignments.unassigned"))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  if ((screens.data ?? []).length === 0) {
    return <p className="py-10 text-center text-muted-foreground">{t("assignments.empty")}</p>
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {(screens.data ?? []).map((screen) => {
        const ofScreen = (assignments.data ?? []).filter((a) => a.screen_id === screen.id)
        const assignedEmails = new Set(ofScreen.map((a) => a.assignee_email))
        return (
          <Card key={screen.id}>
            <CardHeader className="flex flex-row items-start justify-between gap-2">
              <div className="min-w-0">
                <CardTitle className="truncate">{screen.name}</CardTitle>
                <p className="font-mono text-xs text-muted-foreground">{screen.id}</p>
              </div>
              {canManage && (
                <AssignDialog
                  projectId={projectId}
                  screen={screen}
                  availableTesters={activeTesters.filter((m) => !assignedEmails.has(m.email))}
                />
              )}
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {ofScreen.length === 0 && (
                <p className="text-sm text-muted-foreground">{t("assignments.notAssigned")}</p>
              )}
              {ofScreen.map((assignment) => (
                <div
                  key={assignment.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2"
                >
                  <span className="text-sm font-medium">
                    {memberByEmail.get(assignment.assignee_email)?.name ?? assignment.assignee_email}
                  </span>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={assignment.status} />
                    <DeadlineBadge deadline={assignment.deadline} />
                    {canManage && (
                      <ConfirmDialog
                        trigger={
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            aria-label={t("assignments.unassign")}
                          />
                        }
                        triggerLabel={<X />}
                        title={t("assignments.unassign")}
                        description={`${screen.name}: ${assignment.assignee_email}`}
                        onConfirm={() => remove(assignment.id)}
                      />
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

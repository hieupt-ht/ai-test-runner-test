"use client"

import { ChevronDown, ChevronRight, Pencil, Trash2, UserMinus, UserPlus } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { ModuleFormDialog } from "@/components/modules/module-form-dialog"
import { ModuleWorkDialog } from "@/components/modules/module-work-dialog"
import { Button } from "@/components/ui/button"
import type { MemberView, ModuleView, ModuleWorker, Screen } from "@/lib/api/types"
import { useDeleteModule, useUnassignModule } from "@/lib/use-modules"
import { useAssignments } from "@/lib/use-project-data"

/** "2026-12-20" -> "20/12" */
function shortDate(deadline: string): string {
  const [, month, day] = deadline.split("-")
  return `${day}/${month}`
}

type Props = {
  projectId: string
  module: ModuleView
  /** Các màn hình thuộc module (để đếm việc giao khi bỏ nhận) */
  screens: Screen[]
  /** Tester đang hoạt động trong dự án (cho hộp thoại giao) */
  testers: MemberView[]
  /** QA Lead/Admin: được giao, sửa, xoá module */
  canManage: boolean
  /** Tester: được tự nhận / bỏ nhận */
  canClaim: boolean
  meEmail: string
  defaultOpen?: boolean
  /** Bảng màn hình của module */
  children?: React.ReactNode
}

export function ModuleSection({
  projectId,
  module,
  screens,
  testers,
  canManage,
  canClaim,
  meEmail,
  defaultOpen = true,
  children,
}: Props) {
  const t = useTranslations("modules")
  const tCommon = useTranslations("common")
  const [open, setOpen] = useState(defaultOpen)
  const assignments = useAssignments(projectId)
  const unassign = useUnassignModule(projectId)
  const deleteModule = useDeleteModule(projectId)

  const screenIds = new Set(screens.map((screen) => screen.id))
  const iWork = module.workers.some((worker) => worker.email === meEmail)

  /** Số màn hình trong module mà `email` đang có việc giao. */
  function assignedCount(email: string): number {
    return (assignments.data ?? []).filter(
      (item) => item.assignee_email === email && screenIds.has(item.screen_id),
    ).length
  }

  async function removeWorker(worker: ModuleWorker) {
    try {
      await unassign.mutateAsync({ moduleId: module.id, workerId: worker.assignment_id })
      toast.success(t("unclaimed"))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  async function remove() {
    try {
      await deleteModule.mutateAsync(module.id)
      toast.success(tCommon("deleted"))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  function unclaimButton(worker: ModuleWorker, label: React.ReactNode) {
    return (
      <ConfirmDialog
        trigger={<Button size="sm" variant="outline" />}
        triggerLabel={label}
        title={t("unclaimTitle", { name: module.name })}
        description={t("unclaimConfirm", { count: assignedCount(worker.email) })}
        onConfirm={() => removeWorker(worker)}
      />
    )
  }

  const myWorker = module.workers.find((worker) => worker.email === meEmail)

  return (
    <section className="flex flex-col gap-2 rounded-lg border p-3" id={module.id}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          aria-expanded={open}
          aria-label={t("expand")}
          onClick={() => setOpen((value) => !value)}
          className="flex min-w-0 items-center gap-2 text-left"
        >
          {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          <span className="truncate font-medium">{module.name}</span>
          <span className="font-mono text-xs text-muted-foreground">{module.id}</span>
          <span className="text-xs text-muted-foreground">
            {t("screenCount", { count: module.screen_count })}
          </span>
        </button>

        <div className="flex flex-wrap items-center gap-2">
          {canManage && (
            <>
              <ModuleWorkDialog
                projectId={projectId}
                module={module}
                mode="assign"
                testers={testers}
                meEmail={meEmail}
                trigger={<Button size="sm" variant="outline" />}
                triggerLabel={
                  <>
                    <UserPlus /> {t("assign")}
                  </>
                }
              />
              <ModuleFormDialog
                projectId={projectId}
                module={module}
                trigger={<Button variant="ghost" size="icon-sm" aria-label={tCommon("edit")} />}
                triggerLabel={<Pencil />}
              />
              <ConfirmDialog
                trigger={<Button variant="ghost" size="icon-sm" aria-label={tCommon("delete")} />}
                triggerLabel={<Trash2 />}
                title={t("deleteTitle", { id: module.id })}
                description={t("deleteConfirm")}
                onConfirm={remove}
              />
            </>
          )}
          {canClaim &&
            (iWork && myWorker ? (
              unclaimButton(
                myWorker,
                <>
                  <UserMinus /> {t("unclaim")}
                </>,
              )
            ) : (
              <ModuleWorkDialog
                projectId={projectId}
                module={module}
                mode="claim"
                testers={testers}
                meEmail={meEmail}
                trigger={<Button size="sm" />}
                triggerLabel={
                  <>
                    <UserPlus /> {t("claim")}
                  </>
                }
              />
            ))}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        {module.workers.length === 0
          ? t("nobody")
          : t("working", {
              names: module.workers
                .map((worker) => `${worker.name} (${shortDate(worker.deadline)})`)
                .join(", "),
            })}
      </p>

      {open && children}
    </section>
  )
}

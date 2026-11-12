"use client"

import { Pencil, Plus, Trash2 } from "lucide-react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { ScreenFormDialog } from "@/components/screens/screen-form-dialog"
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
import { useDeleteScreen, useScreens } from "@/lib/use-project-data"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"

export default function ScreensPage() {
  const t = useTranslations()
  const projectId = useProjectId()
  const { data: project } = useProject(projectId)
  const screensQuery = useScreens(projectId)
  const deleteScreen = useDeleteScreen(projectId)

  const canManage = Boolean(project?.permissions.includes("MANAGE_SCREENS")) && !project?.archived
  const screens = screensQuery.data ?? []

  async function remove(screenId: string) {
    try {
      await deleteScreen.mutateAsync(screenId)
      toast.success(t("common.deleted"))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  if (screensQuery.isLoading) return <Skeleton className="h-48 w-full" />

  return (
    <div className="flex flex-col gap-4">
      {canManage && (
        <div className="flex justify-end">
          <ScreenFormDialog
            projectId={projectId}
            trigger={<Button />}
            triggerLabel={
              <>
                <Plus /> {t("screens.add")}
              </>
            }
          />
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">{t("screens.colId")}</TableHead>
              <TableHead>{t("screens.colName")}</TableHead>
              <TableHead>{t("screens.colRoute")}</TableHead>
              <TableHead>{t("screens.colCodePaths")}</TableHead>
              {canManage && <TableHead className="w-24" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {screens.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  {t("screens.empty")}
                </TableCell>
              </TableRow>
            )}
            {screens.map((screen) => (
              <TableRow key={screen.id}>
                <TableCell className="font-mono text-xs text-muted-foreground">{screen.id}</TableCell>
                <TableCell>
                  <div className="font-medium">{screen.name}</div>
                  {screen.description && (
                    <div className="line-clamp-1 text-xs text-muted-foreground">
                      {screen.description}
                    </div>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs">{screen.route}</TableCell>
                <TableCell
                  className="text-xs text-muted-foreground"
                  title={screen.code_paths.join("\n")}
                >
                  {t("screens.pathCount", { count: screen.code_paths.length })}
                </TableCell>
                {canManage && (
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <ScreenFormDialog
                        projectId={projectId}
                        screen={screen}
                        trigger={<Button variant="ghost" size="icon" aria-label={t("common.edit")} />}
                        triggerLabel={<Pencil />}
                      />
                      <ConfirmDialog
                        trigger={
                          <Button variant="ghost" size="icon" aria-label={t("common.delete")} />
                        }
                        triggerLabel={<Trash2 />}
                        title={t("screens.deleteTitle", { id: screen.id })}
                        description={t("screens.deleteConfirm")}
                        onConfirm={() => remove(screen.id)}
                      />
                    </div>
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

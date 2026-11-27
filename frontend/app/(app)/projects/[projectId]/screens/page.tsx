"use client"

import { Pencil, Plus, Trash2 } from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { ModuleFormDialog } from "@/components/modules/module-form-dialog"
import { ModuleSection } from "@/components/modules/module-section"
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
import type { Screen } from "@/lib/api/types"
import { useMe } from "@/lib/use-me"
import { useModules } from "@/lib/use-modules"
import { useDeleteScreen, useMembers, useScreens } from "@/lib/use-project-data"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"
import { useTestCases } from "@/lib/use-test-cases"

export default function ScreensPage() {
  const t = useTranslations()
  const projectId = useProjectId()
  const openModule = useSearchParams().get("module")
  const { user } = useMe()
  const { data: project } = useProject(projectId)
  const screensQuery = useScreens(projectId)
  const modulesQuery = useModules(projectId)
  const membersQuery = useMembers(projectId)
  const deleteScreen = useDeleteScreen(projectId)
  const casesQuery = useTestCases(projectId)
  // Đếm số case theo màn hình để hiện cạnh tên màn hình.
  const caseCounts = new Map<string, number>()
  for (const testCase of casesQuery.data ?? []) {
    caseCounts.set(testCase.screen_id, (caseCounts.get(testCase.screen_id) ?? 0) + 1)
  }

  const canManage = Boolean(project?.permissions.includes("MANAGE_SCREENS")) && !project?.archived
  const canClaim = user?.role === "TESTER" && !canManage && !project?.archived
  const screens = screensQuery.data ?? []
  const modules = modulesQuery.data ?? []
  const testers = (membersQuery.data ?? []).filter((m) => m.role === "TESTER" && m.active)
  const loose = screens.filter((screen) => !modules.some((module) => module.id === screen.module_id))

  async function remove(screenId: string) {
    try {
      await deleteScreen.mutateAsync(screenId)
      toast.success(t("common.deleted"))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  if (screensQuery.isLoading || modulesQuery.isLoading) {
    return <Skeleton className="h-48 w-full" />
  }

  function screenTable(list: Screen[]) {
    return (
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">{t("screens.colId")}</TableHead>
              <TableHead>{t("screens.colName")}</TableHead>
              <TableHead>{t("screens.colRoute")}</TableHead>
              <TableHead>{t("screens.colDevOwner")}</TableHead>
              <TableHead>{t("screens.colCodePaths")}</TableHead>
              <TableHead>{t("screens.colCases")}</TableHead>
              {canManage && <TableHead className="w-24" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {list.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-6 text-center text-muted-foreground">
                  {t("screens.empty")}
                </TableCell>
              </TableRow>
            )}
            {list.map((screen) => (
              <TableRow key={screen.id}>
                <TableCell className="font-mono text-xs text-muted-foreground">{screen.id}</TableCell>
                <TableCell>
                  <Link
                    href={`/projects/${projectId}/screens/${screen.id}`}
                    className="font-medium underline-offset-2 hover:underline"
                  >
                    {screen.name}
                  </Link>
                  {screen.description && (
                    <div className="line-clamp-1 text-xs text-muted-foreground">
                      {screen.description}
                    </div>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs">{screen.route}</TableCell>
                <TableCell className="text-xs">
                  {screen.dev_owner ? (
                    `@${screen.dev_owner}`
                  ) : (
                    <span className="text-muted-foreground">{t("screens.noDevOwner")}</span>
                  )}
                </TableCell>
                <TableCell
                  className="text-xs text-muted-foreground"
                  title={screen.code_paths.join("\n")}
                >
                  {t("screens.pathCount", { count: screen.code_paths.length })}
                </TableCell>
                <TableCell className="text-xs">
                  <Link
                    href={`/projects/${projectId}/test-cases?screen=${screen.id}`}
                    className="underline-offset-2 hover:underline"
                  >
                    {t("testCases.caseCount", { count: caseCounts.get(screen.id) ?? 0 })}
                  </Link>
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
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {(canManage || canClaim) && (
        <div className="flex justify-end gap-2">
          <ModuleFormDialog
            projectId={projectId}
            trigger={<Button variant="outline" />}
            triggerLabel={
              <>
                <Plus /> {t("modules.add")}
              </>
            }
          />
          {canManage && (
            <ScreenFormDialog
              projectId={projectId}
              trigger={<Button />}
              triggerLabel={
                <>
                  <Plus /> {t("screens.add")}
                </>
              }
            />
          )}
        </div>
      )}

      {modules.map((module) => (
        <ModuleSection
          key={module.id}
          projectId={projectId}
          module={module}
          screens={screens.filter((screen) => screen.module_id === module.id)}
          testers={testers}
          canManage={canManage}
          canClaim={canClaim}
          meEmail={user?.email ?? ""}
          defaultOpen={!openModule || openModule === module.id}
        >
          {screenTable(screens.filter((screen) => screen.module_id === module.id))}
        </ModuleSection>
      ))}

      {(loose.length > 0 || modules.length === 0) && (
        <section className="flex flex-col gap-2">
          {modules.length > 0 && (
            <h2 className="text-sm font-medium text-muted-foreground">
              {t("modules.unassignedTitle")}
            </h2>
          )}
          {screenTable(loose)}
        </section>
      )}
    </div>
  )
}

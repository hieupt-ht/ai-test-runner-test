"use client"

import { ArrowLeft, Pencil, Plus } from "lucide-react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { Suspense } from "react"

import { ScreenFormDialog } from "@/components/screens/screen-form-dialog"
import { ScreenMediaStrip } from "@/components/screens/screen-media-strip"
import { CaseStatusBadge } from "@/components/test-cases/status-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { selectableScreens } from "@/lib/test-cases/selectable-screens"
import { useMe } from "@/lib/use-me"
import { useAssignments, useScreens } from "@/lib/use-project-data"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"
import { useTestCases } from "@/lib/use-test-cases"

// useParams cần nằm trong <Suspense> vì đang bật cacheComponents.
export default function ScreenDetailPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ScreenDetailView />
    </Suspense>
  )
}

function ScreenDetailView() {
  const t = useTranslations()
  const router = useRouter()
  const projectId = useProjectId()
  const { screenId } = useParams<{ screenId: string }>()
  const { data: project } = useProject(projectId)
  const { user } = useMe()
  const screensQuery = useScreens(projectId)
  const assignmentsQuery = useAssignments(projectId)
  const casesQuery = useTestCases(projectId)

  if (screensQuery.isLoading) return <Skeleton className="h-96 w-full" />

  const backLink = (
    <Link
      href={`/projects/${projectId}/screens`}
      className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" /> {t("screens.back")}
    </Link>
  )

  const screens = screensQuery.data ?? []
  const current = screens.find((item) => item.id === screenId)
  if (!current) {
    return (
      <div className="flex flex-col gap-3">
        {backLink}
        <p className="text-muted-foreground">{t("screens.notFound")}</p>
      </div>
    )
  }

  const active = !project?.archived
  const canManage = Boolean(project?.permissions.includes("MANAGE_SCREENS")) && active
  const canEditCases = Boolean(project?.permissions.includes("EDIT_TEST_CASE")) && active
  const canCreateHere =
    canEditCases &&
    selectableScreens(screens, assignmentsQuery.data ?? [], user).some(
      (item) => item.id === current.id,
    )
  const cases = (casesQuery.data ?? [])
    .filter((item) => item.screen_id === current.id)
    .sort((a, b) => a.id.localeCompare(b.id))

  return (
    <div className="flex flex-col gap-4">
      {backLink}

      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <p className="font-mono text-xs text-muted-foreground">{current.id}</p>
          <h2 className="text-xl font-semibold">{current.name}</h2>
          <p className="font-mono text-xs">{current.route}</p>
          {current.dev_owner && <p className="text-xs">@{current.dev_owner}</p>}
        </div>
        <div className="flex gap-2">
          {canManage && (
            <ScreenFormDialog
              projectId={projectId}
              screen={current}
              trigger={<Button variant="outline" />}
              triggerLabel={
                <>
                  <Pencil /> {t("common.edit")}
                </>
              }
            />
          )}
          {canCreateHere && (
            <Link
              href={`/projects/${projectId}/test-cases/new?screen=${current.id}`}
              className={buttonVariants()}
            >
              <Plus /> {t("screens.createCase")}
            </Link>
          )}
        </div>
      </div>

      {current.description && <p className="text-sm">{current.description}</p>}
      <ScreenMediaStrip media={current.media ?? []} />

      <h3 className="font-medium">{t("screens.casesTitle", { count: cases.length })}</h3>
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-28">{t("testCases.colId")}</TableHead>
              <TableHead>{t("testCases.colTitle")}</TableHead>
              <TableHead>{t("testCases.colStatus")}</TableHead>
              <TableHead>{t("testCases.colSeverity")}</TableHead>
              <TableHead>{t("testCases.form.platform")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                  {t("screens.noCases")}
                </TableCell>
              </TableRow>
            )}
            {cases.map((testCase) => (
              <TableRow
                key={testCase.id}
                className="cursor-pointer"
                onClick={(event) => {
                  // Bấm thẳng vào link mã case thì để link tự chuyển trang.
                  if ((event.target as HTMLElement).closest("a")) return
                  router.push(`/projects/${projectId}/test-cases/${testCase.id}`)
                }}
              >
                <TableCell className="font-mono text-xs">
                  <Link
                    href={`/projects/${projectId}/test-cases/${testCase.id}`}
                    className="underline-offset-2 hover:underline"
                  >
                    {testCase.id}
                  </Link>
                </TableCell>
                <TableCell className="font-medium">{testCase.title}</TableCell>
                <TableCell>
                  <CaseStatusBadge status={testCase.status} />
                </TableCell>
                <TableCell>{t(`testCases.severity.${testCase.severity}`)}</TableCell>
                <TableCell>{t(`testCases.platform.${testCase.platform}`)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

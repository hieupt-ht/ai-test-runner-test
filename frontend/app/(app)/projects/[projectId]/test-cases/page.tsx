"use client"

import { FileUp, Plus, RefreshCw } from "lucide-react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useFormatter, useTranslations } from "next-intl"
import { Suspense, useMemo, useState } from "react"
import { toast } from "sonner"

import { BulkApproveBar } from "@/components/test-cases/bulk-approve-bar"
import { FiltersBar } from "@/components/test-cases/filters-bar"
import { ImportDialog } from "@/components/test-cases/import-dialog"
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
import { filterTestCases, paginate, type CaseFilters } from "@/lib/test-cases/filter"
import { approvableIds, batchItems, toggleAll, toggleId } from "@/lib/test-cases/selection"
import { selectableScreens } from "@/lib/test-cases/selectable-screens"
import { useMe } from "@/lib/use-me"
import { useResults } from "@/lib/use-results"
import { useAssignments, useScreens } from "@/lib/use-project-data"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"
import { useSyncIssues, useTestCases } from "@/lib/use-test-cases"

const PAGE_SIZE = 25

// useSearchParams (đọc ?screen=) cần nằm trong <Suspense> vì đang bật cacheComponents.
export default function TestCasesPage() {
  return (
    <Suspense fallback={<Skeleton className="h-48 w-full" />}>
      <TestCaseList />
    </Suspense>
  )
}

function TestCaseList() {
  const t = useTranslations("testCases")
  const format = useFormatter()
  const projectId = useProjectId()
  const searchParams = useSearchParams()
  const router = useRouter()
  const { data: project } = useProject(projectId)
  const [includeArchived, setIncludeArchived] = useState(searchParams.get("include_archived") === "true")
  const casesQuery = useTestCases(projectId, includeArchived)
  const syncIssues = useSyncIssues(projectId)
  const screensQuery = useScreens(projectId)
  const assignmentsQuery = useAssignments(projectId)
  const { user: me } = useMe()
  const [importOpen, setImportOpen] = useState(false)
  // Kết quả gần nhất của từng case: một request cho cả danh sách (không gọi mỗi dòng)
  const resultsQuery = useResults(projectId)

  // ?screen=SC-0001 chỉ đặt bộ lọc ban đầu; sau đó người dùng tự đổi trong thanh lọc.
  const [filters, setFilters] = useState<CaseFilters>({
    query: "",
    screenId: searchParams.get("screen") ?? undefined,
  })
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set())

  const cases = useMemo(() => casesQuery.data ?? [], [casesQuery.data])
  const screens = screensQuery.data ?? []
  const lastResults = useMemo(
    () => new Map((resultsQuery.data ?? []).map((item) => [item.case_id, item.status])),
    [resultsQuery.data],
  )
  const screenNames = new Map(screens.map((screen) => [screen.id, screen.name]))
  const creators = useMemo(
    () => [...new Set(cases.map((testCase) => testCase.created_by))].sort(),
    [cases],
  )

  const filtered = useMemo(() => filterTestCases(cases, filters), [cases, filters])
  // Lọc xong có thể còn ít trang hơn trang đang xem, nên kẹp về trang cuối.
  const { pageCount } = paginate(filtered, 1, PAGE_SIZE)
  const currentPage = Math.min(page, pageCount)
  const { items: visible } = paginate(filtered, currentPage, PAGE_SIZE)

  // Chỉ case Chờ duyệt (trong bộ lọc hiện tại, mọi trang) mới chọn để duyệt hàng loạt được.
  const approvable = useMemo(() => approvableIds(filtered), [filtered])
  const items = useMemo(() => batchItems(selected, cases), [selected, cases])
  const allApprovableSelected = approvable.length > 0 && approvable.every((id) => selected.has(id))
  const canReview = Boolean(project?.permissions.includes("REVIEW_TEST_CASE")) && !project?.archived
  const columnCount = canReview ? 10 : 9

  const canCreate = Boolean(project?.permissions.includes("EDIT_TEST_CASE")) && !project?.archived
  // Nhập từ Excel cũng là tạo case: tester chỉ nhập được khi có ít nhất một màn hình được giao.
  const canImport =
    canCreate && selectableScreens(screens, assignmentsQuery.data ?? [], me).length > 0

  if (casesQuery.isLoading) return <Skeleton className="h-48 w-full" />
  if (casesQuery.isError) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="text-sm text-destructive">
          {t("loadFailed", { message: casesQuery.error.message })}
        </p>
        <Button variant="outline" size="sm" onClick={() => void casesQuery.refetch()}>
          {t("retry")}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <FiltersBar
          filters={filters}
          onChange={(next) => {
            setFilters(next)
            setPage(1)
          }}
          screens={screens}
          creators={creators}
        />
        <div className="flex flex-wrap gap-2">
          <label className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(event) => setIncludeArchived(event.target.checked)}
            />
            {t("includeArchived")}
          </label>
          {canReview && (
            <Button
              variant="outline"
              disabled={syncIssues.isPending}
              onClick={async () => {
                try {
                  const result = await syncIssues.mutateAsync()
                  const message = t("sync.result", {
                    created: result.created,
                    updated: result.updated + result.closed + result.reopened,
                    failed: result.failed?.length ?? 0,
                  })
                  if (result.failed?.length) toast.warning(message)
                  else toast.success(message)
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : String(error))
                }
              }}
            >
              <RefreshCw className={syncIssues.isPending ? "animate-spin" : ""} />
              {t("sync.action")}
            </Button>
          )}
          {canImport && (
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <FileUp /> {t("import.action")}
            </Button>
          )}
          {canCreate && (
            <Link
              href={`/projects/${projectId}/test-cases/new${
                filters.screenId ? `?screen=${filters.screenId}` : ""
              }`}
              className={buttonVariants()}
            >
              <Plus /> {t("add")}
            </Link>
          )}
        </div>
      </div>

      <ImportDialog projectId={projectId} open={importOpen} onOpenChange={setImportOpen} />

      {canReview && (
        <BulkApproveBar
          projectId={projectId}
          items={items}
          onDone={() => setSelected(new Set())}
          onClear={() => setSelected(new Set())}
          reviewDisabled={project ? !project.require_review : false}
        />
      )}

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              {canReview && (
                <TableHead className="w-8">
                  <input
                    type="checkbox"
                    aria-label={t("bulk.selectAll")}
                    title={t("bulk.selectAll")}
                    checked={allApprovableSelected}
                    disabled={approvable.length === 0}
                    onChange={() => setSelected((current) => toggleAll(current, approvable))}
                  />
                </TableHead>
              )}
              <TableHead className="w-28">{t("colId")}</TableHead>
              <TableHead>{t("colTitle")}</TableHead>
              <TableHead>{t("colScreen")}</TableHead>
              <TableHead>{t("colSeverity")}</TableHead>
              <TableHead>{t("colPriority")}</TableHead>
              <TableHead>{t("colExecutionMode")}</TableHead>
              <TableHead>{t("colStatus")}</TableHead>
              <TableHead>{t("colCreator")}</TableHead>
              <TableHead>{t("colUpdatedAt")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={columnCount} className="py-10 text-center text-muted-foreground">
                  {cases.length === 0 ? t(canCreate ? "emptyCanCreate" : "empty") : t("emptyFiltered")}
                </TableCell>
              </TableRow>
            )}
            {visible.map((testCase) => (
              <TableRow
                key={testCase.id}
                className="cursor-pointer"
                onClick={(event) => {
                  // Bấm thẳng vào link mã case thì để link tự chuyển trang (giữ Ctrl+click mở tab mới).
                  if ((event.target as HTMLElement).closest("a, input")) return
                  router.push(`/projects/${projectId}/test-cases/${testCase.id}`)
                }}
              >
                {canReview && (
                  <TableCell>
                    {testCase.status === "IN_REVIEW" && (
                      <input
                        type="checkbox"
                        aria-label={t("bulk.selectCase", { id: testCase.id })}
                        checked={selected.has(testCase.id)}
                        onChange={() => setSelected((current) => toggleId(current, testCase.id))}
                      />
                    )}
                  </TableCell>
                )}
                <TableCell className="font-mono text-xs">
                  <Link
                    href={`/projects/${projectId}/test-cases/${testCase.id}`}
                    className="underline-offset-2 hover:underline"
                  >
                    {testCase.id}
                  </Link>
                </TableCell>
                <TableCell className="font-medium">{testCase.title}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {testCase.screen_id} · {screenNames.get(testCase.screen_id) ?? ""}
                </TableCell>
                <TableCell>{t(`severity.${testCase.severity}`)}</TableCell>
                <TableCell>{testCase.priority}</TableCell>
                <TableCell className="text-xs">{t(`executionMode.${testCase.execution_mode}`)}</TableCell>
                <TableCell>
                  <CaseStatusBadge
                    status={testCase.status}
                    lastResult={lastResults.get(testCase.id)}
                  />
                </TableCell>
                <TableCell className="text-xs">{testCase.created_by}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {format.dateTime(new Date(testCase.updated_at), {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage <= 1}
            onClick={() => setPage(currentPage - 1)}
          >
            {t("prevPage")}
          </Button>
          <span className="text-muted-foreground">
            {t("pageOf", { page: currentPage, count: pageCount })}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={currentPage >= pageCount}
            onClick={() => setPage(currentPage + 1)}
          >
            {t("nextPage")}
          </Button>
        </div>
      )}
    </div>
  )
}

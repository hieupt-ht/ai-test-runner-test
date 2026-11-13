"use client"

import { Plus } from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useFormatter, useTranslations } from "next-intl"
import { Suspense, useMemo, useState } from "react"

import { FiltersBar } from "@/components/test-cases/filters-bar"
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
import { useScreens } from "@/lib/use-project-data"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"
import { useTestCases } from "@/lib/use-test-cases"

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
  const { data: project } = useProject(projectId)
  const casesQuery = useTestCases(projectId)
  const screensQuery = useScreens(projectId)

  // ?screen=SC-0001 chỉ đặt bộ lọc ban đầu; sau đó người dùng tự đổi trong thanh lọc.
  const [filters, setFilters] = useState<CaseFilters>({
    query: "",
    screenId: searchParams.get("screen") ?? undefined,
  })
  const [page, setPage] = useState(1)

  const cases = useMemo(() => casesQuery.data ?? [], [casesQuery.data])
  const screens = screensQuery.data ?? []
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

  const canCreate = Boolean(project?.permissions.includes("EDIT_TEST_CASE")) && !project?.archived

  if (casesQuery.isLoading) return <Skeleton className="h-48 w-full" />

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

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-28">{t("colId")}</TableHead>
              <TableHead>{t("colTitle")}</TableHead>
              <TableHead>{t("colScreen")}</TableHead>
              <TableHead>{t("colSeverity")}</TableHead>
              <TableHead>{t("colPriority")}</TableHead>
              <TableHead>{t("colStatus")}</TableHead>
              <TableHead>{t("colCreator")}</TableHead>
              <TableHead>{t("colUpdatedAt")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="py-10 text-center text-muted-foreground">
                  {cases.length === 0 ? t(canCreate ? "emptyCanCreate" : "empty") : t("emptyFiltered")}
                </TableCell>
              </TableRow>
            )}
            {visible.map((testCase) => (
              <TableRow key={testCase.id}>
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
                <TableCell>
                  <CaseStatusBadge status={testCase.status} />
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

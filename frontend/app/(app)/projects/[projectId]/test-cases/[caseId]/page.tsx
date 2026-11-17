"use client"

import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { Suspense, useState } from "react"

import { CaseForm } from "@/components/test-cases/case-form"
import { ArchiveAction } from "@/components/test-cases/archive-action"
import { CaseReadOnly } from "@/components/test-cases/case-read-only"
import { HistoryPanel, commentOf } from "@/components/test-cases/history-panel"
import { ReviewActions } from "@/components/test-cases/review-actions"
import { CaseStatusBadge } from "@/components/test-cases/status-badge"
import { Skeleton } from "@/components/ui/skeleton"
import { latestReturn } from "@/lib/test-cases/returned"
import { useProjectId } from "@/lib/use-project-id"
import { useProject } from "@/lib/use-projects"
import { useCaseHistory, useTestCase } from "@/lib/use-test-cases"

export default function TestCaseDetailPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <TestCaseDetailView />
    </Suspense>
  )
}

function TestCaseDetailView() {
  const t = useTranslations("testCases")
  const projectId = useProjectId()
  const { caseId } = useParams<{ caseId: string }>()
  const caseQuery = useTestCase(projectId, caseId)
  const historyQuery = useCaseHistory(projectId, caseId)
  const { data: project } = useProject(projectId)
  const reviewEnabled = project?.require_review ?? true
  const [formDirty, setFormDirty] = useState(false)

  if (caseQuery.isLoading) return <Skeleton className="h-96 w-full" />
  const testCase = caseQuery.data
  if (!testCase) {
    return <p className="text-muted-foreground">{caseQuery.error?.message ?? t("detail.notFound")}</p>
  }

  const history = historyQuery.data ?? []
  // Case đang ở Nháp mà từng bị trả lại thì cho người viết thấy nhận xét ngay đầu trang.
  const returned = testCase.status === "DRAFT" ? latestReturn(history) : undefined
  const editable = testCase.can_edit && !["DEPRECATED", "ARCHIVED"].includes(testCase.status)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Link
        href={`/projects/${projectId}/test-cases`}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {t("back")}
      </Link>

      {returned && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-500/40 dark:bg-amber-500/10">
          <p className="font-medium">{t("detail.returnedBanner")}</p>
          <p className="text-xs text-muted-foreground">{t("detail.returnedBy", { actor: returned.actor })}</p>
          <p className="mt-1 whitespace-pre-wrap">{commentOf(returned)}</p>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-muted-foreground">{testCase.id}</span>
          <CaseStatusBadge status={testCase.status} />
          <span className="text-xs text-muted-foreground">
            {t("detail.version", { version: testCase.version })}
          </span>
        </div>
        <ReviewActions
          projectId={projectId}
          testCase={testCase}
          hideSubmit={editable}
          formDirty={editable && formDirty}
          reviewDisabled={!reviewEnabled}
        />
        <ArchiveAction projectId={projectId} testCase={testCase} />
      </div>

      {testCase.status === "DEPRECATED" && (
        <p className="text-sm text-muted-foreground">{t("detail.deprecatedHint")}</p>
      )}

      {editable ? (
        // key đổi khi case có phiên bản mới (sau khi lưu / duyệt / tải lại) để form nạp lại dữ liệu.
        <CaseForm
          key={`${testCase.id}-${testCase.version}`}
          projectId={projectId}
          testCase={testCase}
          onDirtyChange={setFormDirty}
          reviewEnabled={reviewEnabled}
        />
      ) : (
        <>
          {!testCase.can_edit && (
            <p className="text-sm text-muted-foreground">{t("detail.readOnlyHint")}</p>
          )}
          <CaseReadOnly testCase={testCase} />
        </>
      )}

      <HistoryPanel history={history} />
    </div>
  )
}

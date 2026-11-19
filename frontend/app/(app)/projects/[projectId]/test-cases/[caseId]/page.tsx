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
import { ManualRunPanel } from "@/components/test-cases/manual-run-panel"
import { ReviewActions } from "@/components/test-cases/review-actions"
import { CaseStatusBadge } from "@/components/test-cases/status-badge"
import { Skeleton } from "@/components/ui/skeleton"
import { formatVietnamTime } from "@/lib/test-cases/history"
import { latestReturn } from "@/lib/test-cases/returned"
import { useScreens } from "@/lib/use-project-data"
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
  const screens = useScreens(projectId).data ?? []
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
  // Khung chạy test tay: case Manual đang Nháp/Đã kiểm thử, người có quyền sửa, dự án chưa lưu trữ
  const canRun =
    testCase.execution_mode === "MANUAL" &&
    testCase.can_run &&
    !project?.archived &&
    ["DRAFT", "TESTED"].includes(testCase.status)
  // Kết quả gần nhất chỉ có nghĩa khi case đang "Đã kiểm thử" (sửa nội dung thì về Nháp)
  const lastResult = testCase.status === "TESTED" ? testCase.last_result : null
  const devOwner = screens.find((screen) => screen.id === testCase.screen_id)?.dev_owner ?? ""

  return (
    <div className="flex flex-col gap-4">
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
          <CaseStatusBadge status={testCase.status} lastResult={lastResult?.status} />
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

      {lastResult && (
        <p className="text-sm text-muted-foreground">
          {t("detail.lastRun", {
            result: t(`lastResult.${lastResult.status}`),
            runId: lastResult.run_id,
            time: formatVietnamTime(lastResult.created_at),
          })}{" "}
          <Link href={`/projects/${projectId}/results`} className="underline underline-offset-2">
            {t("detail.viewResults")}
          </Link>
        </p>
      )}

      {canRun &&
        (formDirty ? (
          <p className="text-sm text-amber-700 dark:text-amber-300">{t("detail.saveBeforeRun")}</p>
        ) : (
          <ManualRunPanel
            projectId={projectId}
            storage={project?.storage}
            testCase={testCase}
            defaultAssignee={devOwner}
          />
        ))}

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
            <p className="text-sm text-muted-foreground">
              {testCase.can_run ? t("detail.runOnlyHint") : t("detail.readOnlyHint")}
            </p>
          )}
          <CaseReadOnly testCase={testCase} />
        </>
      )}

      <HistoryPanel history={history} />
    </div>
  )
}

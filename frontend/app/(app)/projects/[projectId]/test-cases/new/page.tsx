"use client"

import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { Suspense } from "react"

import { CaseForm } from "@/components/test-cases/case-form"
import { Skeleton } from "@/components/ui/skeleton"
import { selectableScreens } from "@/lib/test-cases/selectable-screens"
import { useMe } from "@/lib/use-me"
import { useAssignments, useScreens } from "@/lib/use-project-data"
import { useProjectId } from "@/lib/use-project-id"

// useSearchParams (đọc ?screen=) cần nằm trong <Suspense> vì đang bật cacheComponents.
export default function NewTestCasePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <NewTestCase />
    </Suspense>
  )
}

function NewTestCase() {
  const t = useTranslations("testCases")
  const projectId = useProjectId()
  const searchParams = useSearchParams()
  const screensQuery = useScreens(projectId)
  const assignmentsQuery = useAssignments(projectId)
  const { user: me, isLoading: meLoading } = useMe()

  if (screensQuery.isLoading || assignmentsQuery.isLoading || meLoading) return <Skeleton className="h-96 w-full" />

  const screens = selectableScreens(screensQuery.data ?? [], assignmentsQuery.data ?? [], me)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Link
        href={`/projects/${projectId}/test-cases`}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {t("back")}
      </Link>
      <h2 className="text-lg font-semibold">{t("createTitle")}</h2>
      <CaseForm
        projectId={projectId}
        screens={screens}
        defaultScreenId={searchParams.get("screen") ?? undefined}
      />
    </div>
  )
}

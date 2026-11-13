"use client"

import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { Suspense } from "react"

import { CaseForm } from "@/components/test-cases/case-form"
import { Skeleton } from "@/components/ui/skeleton"
import { useScreens } from "@/lib/use-project-data"
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

  if (screensQuery.isLoading) return <Skeleton className="h-96 w-full" />

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
        screens={screensQuery.data ?? []}
        defaultScreenId={searchParams.get("screen") ?? undefined}
      />
    </div>
  )
}

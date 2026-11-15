"use client"

import { Archive, ArchiveRestore } from "lucide-react"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import type { TestCaseDetail } from "@/lib/api/types"
import { useArchiveTestCase } from "@/lib/use-test-cases"

export function ArchiveAction({ projectId, testCase }: { projectId: string; testCase: TestCaseDetail }) {
  const t = useTranslations("testCases")
  const archive = useArchiveTestCase(projectId, "archive")
  const unarchive = useArchiveTestCase(projectId, "unarchive")
  const isArchived = testCase.status === "ARCHIVED"
  const canShow = testCase.can_archive && (isArchived || ["APPROVED", "TESTED"].includes(testCase.status))
  if (!canShow) return null

  const mutation = isArchived ? unarchive : archive
  const label = isArchived ? "unarchive" : "archive"

  async function changeState() {
    try {
      await mutation.mutateAsync({ caseId: testCase.id, version: testCase.version })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Button variant="outline" disabled={mutation.isPending} onClick={() => void changeState()}>
      {isArchived ? <ArchiveRestore /> : <Archive />}
      {t(label)}
    </Button>
  )
}

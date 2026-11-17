"use client"

import { useQueryClient } from "@tanstack/react-query"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { ConflictDialog } from "@/components/test-cases/conflict-dialog"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import type { TestCaseDetail } from "@/lib/api/types"
import { availableActions, type CaseAction } from "@/lib/test-cases/actions"
import { conflictFrom } from "@/lib/test-cases/conflict"
import { useTransitionTestCase } from "@/lib/use-test-cases"

const MAX_COMMENT = 1000

type Props = {
  projectId: string
  testCase: TestCaseDetail
  /** Form sửa đang hiện (đã có nút Gửi duyệt riêng) nên ẩn "Gửi duyệt" ở đây */
  hideSubmit?: boolean
  /** Form có thay đổi chưa lưu: khoá các nút để không mất phần đang sửa */
  formDirty?: boolean
  /** Dự án tắt bước duyệt: nút Duyệt/Trả lại mờ đi (backend cũng trả 409) */
  reviewDisabled?: boolean
}

/** Các nút chuyển trạng thái (gửi duyệt, duyệt, trả lại, ngừng dùng, khôi phục) của một case. */
export function ReviewActions({ projectId, testCase, hideSubmit, formDirty, reviewDisabled }: Props) {
  const t = useTranslations("testCases")
  const tCommon = useTranslations("common")
  const queryClient = useQueryClient()
  const transition = useTransitionTestCase(projectId)
  const [returnOpen, setReturnOpen] = useState(false)
  const [comment, setComment] = useState("")
  const [commentTouched, setCommentTouched] = useState(false)
  const [conflictMessage, setConflictMessage] = useState<string | null>(null)

  const actions = availableActions(testCase.status, testCase.can_edit, testCase.can_review).filter(
    (action) => !(hideSubmit && action === "submit"),
  )
  const trimmed = comment.trim()
  const commentError = !trimmed ? "required" : trimmed.length > MAX_COMMENT ? "tooLong" : null

  async function run(action: CaseAction, text = "") {
    try {
      await transition.mutateAsync({ caseId: testCase.id, action, version: testCase.version, comment: text })
      toast.success(t("detail.transitioned"))
      return true
    } catch (error) {
      const conflict = conflictFrom(error)
      // 409 kèm bản mới: hỏi tải lại. Các lỗi khác (trạng thái không hợp lệ, đang bận): toast.
      if (conflict) setConflictMessage(conflict.message)
      else toast.error(error instanceof Error ? error.message : String(error))
      return false
    }
  }

  async function confirmReturn() {
    setCommentTouched(true)
    if (commentError) return
    if (await run("return", trimmed)) {
      setReturnOpen(false)
      setComment("")
      setCommentTouched(false)
    }
  }

  function reload() {
    setConflictMessage(null)
    void queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
  }

  if (actions.length === 0) return null

  return (
    <div className="flex flex-col items-end gap-1">
    <div className="flex flex-wrap gap-2">
      {actions.map((action) => {
        if (action === "return") {
          return (
            <Button
              key={action}
              variant="outline"
              disabled={formDirty || reviewDisabled}
              title={reviewDisabled ? t("reviewOff") : undefined}
              onClick={() => setReturnOpen(true)}
            >
              {t("actions.return")}
            </Button>
          )
        }
        if (action === "deprecate") {
          return (
            <ConfirmDialog
              key={action}
              trigger={<Button variant="outline" disabled={transition.isPending || formDirty} />}
              triggerLabel={t("actions.deprecate")}
              title={t("deprecateDialog.title")}
              description={t("deprecateDialog.description")}
              onConfirm={() => void run("deprecate")}
            />
          )
        }
        return (
          <Button
            key={action}
            disabled={transition.isPending || formDirty || (reviewDisabled && action === "approve")}
            title={reviewDisabled && action === "approve" ? t("reviewOff") : undefined}
            onClick={() => void run(action)}>
            {t(`actions.${action}`)}
          </Button>
        )
      })}

      <Dialog open={returnOpen} onOpenChange={setReturnOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("returnDialog.title")}</DialogTitle>
            <DialogDescription>{t("returnDialog.description")}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <Textarea
              rows={4}
              value={comment}
              aria-label={t("returnDialog.comment")}
              aria-invalid={commentTouched && Boolean(commentError)}
              onChange={(event) => setComment(event.target.value)}
            />
            {commentTouched && commentError && (
              <p className="text-xs text-destructive">{t(`returnDialog.${commentError}`)}</p>
            )}
          </div>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>{tCommon("cancel")}</DialogClose>
            <Button disabled={transition.isPending} onClick={() => void confirmReturn()}>
              {t("returnDialog.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConflictDialog
        message={conflictMessage}
        onReload={reload}
        onClose={() => setConflictMessage(null)}
      />
    </div>
    {formDirty && <p className="text-xs text-muted-foreground">{t("detail.dirtyHint")}</p>}
    </div>
  )
}

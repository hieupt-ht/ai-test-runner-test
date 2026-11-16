import type { TestCaseStatus } from "@/lib/api/types"

export type CaseAction = "submit" | "approve" | "return" | "deprecate" | "restore"

/**
 * Các thao tác chuyển trạng thái được phép — cùng quy tắc với backend:
 * submit DRAFT→IN_REVIEW, approve IN_REVIEW→APPROVED, return IN_REVIEW→DRAFT,
 * deprecate (mọi trạng thái trừ DEPRECATED), restore DEPRECATED→DRAFT.
 */
export function availableActions(
  status: TestCaseStatus,
  canEdit: boolean,
  canReview: boolean,
): CaseAction[] {
  const actions: CaseAction[] = []
  if (status === "DRAFT" && canEdit) actions.push("submit")
  if (status === "IN_REVIEW" && canReview) actions.push("approve", "return")
  if (status !== "DEPRECATED" && canEdit) actions.push("deprecate")
  if (status === "DEPRECATED" && canReview) actions.push("restore")
  return actions
}

import type { Assignment, Screen, User } from "@/lib/api/types"

/**
 * Màn hình mà người dùng được chọn khi tạo test case.
 * Tester chỉ tạo được case trên màn hình được giao cho mình (nếu không server trả 403);
 * các vai trò khác được chọn mọi màn hình.
 */
export function selectableScreens(
  screens: Screen[],
  assignments: Assignment[],
  me: User | null,
): Screen[] {
  if (!me) return []
  if (me.role !== "TESTER") return screens
  const assigned = new Set(
    assignments.filter((a) => a.assignee_email === me.email).map((a) => a.screen_id),
  )
  return screens.filter((screen) => assigned.has(screen.id))
}

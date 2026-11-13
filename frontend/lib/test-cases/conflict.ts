import { ApiError } from "@/lib/api/client"
import type { ConflictResponse, TestCase } from "@/lib/api/types"

/**
 * Nếu lỗi là 409 kèm bản mới nhất (`latest`) thì trả về câu báo + bản đó;
 * ngược lại (lỗi khác, hoặc 409 trạng thái không hợp lệ / đang bận) trả null.
 */
export function conflictFrom(error: unknown): { message: string; latest: TestCase } | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null
  const body = error.body as Partial<ConflictResponse> | undefined
  if (!body || typeof body !== "object" || !body.latest) return null
  return { message: error.message, latest: body.latest }
}

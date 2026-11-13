import { ApiError, errorMessage } from "@/lib/api/client"

const FALLBACK_ERROR = "Có lỗi xảy ra, vui lòng thử lại."

/**
 * Lấy dữ liệu từ kết quả của openapi-fetch; lỗi thì ném ApiError kèm câu báo của backend.
 * Dùng chung cho mọi hook gọi API.
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) {
    throw new ApiError(result.response.status, errorMessage(result.error, FALLBACK_ERROR), result.error)
  }
  return result.data
}

/** Cho các API trả 204 (không có nội dung). */
export function ensureOk(result: { error?: unknown; response: Response }): void {
  if (!result.response.ok) {
    throw new ApiError(result.response.status, errorMessage(result.error, FALLBACK_ERROR), result.error)
  }
}

import createClient, { type Middleware } from "openapi-fetch"

import type { paths } from "@/lib/api/schema"

/** Lỗi trả về từ API, giữ nguyên câu báo lỗi tiếng Việt của backend. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    /** Nội dung JSON lỗi gốc, ví dụ 409 kèm `latest` khi bị xung đột. */
    public readonly body?: unknown,
  ) {
    super(message)
  }
}

// Hết phiên đăng nhập thì đưa người dùng về trang đăng nhập.
const redirectOnUnauthorized: Middleware = {
  onResponse({ response }) {
    const isOnLoginPage = window.location.pathname.startsWith("/login")
    if (response.status === 401 && !isOnLoginPage) {
      // Đây là code ngoài React nên không dùng được useRouter; tải lại hẳn trang đăng nhập.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login"
    }
    return response
  },
}

export const api = createClient<paths>({ baseUrl: "", credentials: "same-origin" })
api.use(redirectOnUnauthorized)

/** Lấy câu báo lỗi từ phản hồi lỗi của FastAPI ({"detail": "..."}). */
export function errorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail
    if (typeof detail === "string") return detail
  }
  return fallback
}

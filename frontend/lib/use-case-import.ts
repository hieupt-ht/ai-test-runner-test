"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { ApiError, errorMessage } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

type ParseResult = components["schemas"]["ParseResult"]
type ImportCreated = components["schemas"]["ImportCreated"]

const FALLBACK_ERROR = "Có lỗi xảy ra, vui lòng thử lại."

function importUrl(projectId: string, action?: "template" | "preview"): string {
  const base = `/api/projects/${encodeURIComponent(projectId)}/test-cases/import`
  return action ? `${base}/${action}` : base
}

/** Đường dẫn tải file Excel mẫu (dùng cho thẻ <a download>). */
export function templateUrl(projectId: string): string {
  return importUrl(projectId, "template")
}

/** File kèm module muốn nhập vào ("" = không theo module, như cũ). */
export type ImportInput = { file: File; moduleId: string }

/** Gửi file lên backend (multipart, trường `file` và `module_id`); lỗi thì ném ApiError, giữ nguyên body gốc. */
async function postFile<T>(url: string, { file, moduleId }: ImportInput): Promise<T> {
  const form = new FormData()
  form.append("file", file)
  form.append("module_id", moduleId)
  const response = await fetch(url, { method: "POST", body: form, credentials: "same-origin" })
  const body: unknown = await response.json().catch(() => undefined)
  if (!response.ok) {
    // 422 mang theo `errors` trong body để màn hình hiện từng dòng lỗi.
    throw new ApiError(response.status, errorMessage(body, FALLBACK_ERROR), body)
  }
  return body as T
}

/** Xem trước file: chỉ kiểm tra, chưa tạo gì. */
export function usePreviewImport(projectId: string) {
  return useMutation<ParseResult, ApiError, ImportInput>({
    mutationFn: (input) => postFile<ParseResult>(importUrl(projectId, "preview"), input),
  })
}

/** Nhập thật; xong thì làm mới dữ liệu của dự án. */
export function useImportCases(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation<ImportCreated, ApiError, ImportInput>({
    mutationFn: (input) => postFile<ImportCreated>(importUrl(projectId), input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
      // Số case trên "Việc của tôi" cũng đổi theo
      void queryClient.invalidateQueries({ queryKey: ["me", "assignments"] })
    },
  })
}

"use client"

import { useParams } from "next/navigation"

/**
 * Mã dự án lấy từ URL /projects/<projectId>/...
 *
 * Lưu ý: đang bật cacheComponents, nên component nào gọi hook này phải nằm trong <Suspense>.
 */
export function useProjectId(): string {
  const params = useParams<{ projectId: string }>()
  return params.projectId
}

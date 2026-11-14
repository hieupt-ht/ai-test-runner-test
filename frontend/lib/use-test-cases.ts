"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type {
  AuditEntry,
  BatchApproveResponse,
  TestCase,
  TestCaseContent,
  TestCaseDetail,
  SyncIssuesResult,
} from "@/lib/api/types"
import type { CaseAction } from "@/lib/test-cases/actions"

// Khoá cache bắt đầu bằng ["projects", projectId] nên được làm mới cùng các dữ liệu khác của dự án.
const casesKey = (projectId: string) => ["projects", projectId, "test-cases"] as const
const caseKey = (projectId: string, caseId: string) => [...casesKey(projectId), caseId] as const
const historyKey = (projectId: string, caseId: string) =>
  [...caseKey(projectId, caseId), "history"] as const

export const casePath = (projectId: string, caseId: string) => ({
  params: { path: { project_id: projectId, case_id: caseId } },
})

export function useTestCases(projectId: string) {
  return useQuery({
    queryKey: casesKey(projectId),
    queryFn: async (): Promise<TestCase[]> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/test-cases", {
          params: { path: { project_id: projectId } },
        }),
      ),
  })
}

export function useTestCase(projectId: string, caseId: string) {
  return useQuery({
    queryKey: caseKey(projectId, caseId),
    queryFn: async (): Promise<TestCaseDetail> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/test-cases/{case_id}", casePath(projectId, caseId)),
      ),
  })
}

export function useCaseHistory(projectId: string, caseId: string) {
  return useQuery({
    queryKey: historyKey(projectId, caseId),
    queryFn: async (): Promise<AuditEntry[]> =>
      unwrap(
        await api.GET(
          "/api/projects/{project_id}/test-cases/{case_id}/history",
          casePath(projectId, caseId),
        ),
      ),
  })
}

// ----- Ghi dữ liệu -----

/** `refresh: false` để form tự làm mới sau khi xong cả chuỗi "lưu rồi gửi duyệt". */
type WriteOptions = { refresh?: boolean }

/** Sau khi ghi thì làm mới dữ liệu của dự án và "Việc của tôi" (trạng thái việc có thể đổi theo case). */
export function useRefreshCases(projectId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
    void queryClient.invalidateQueries({ queryKey: ["me", "assignments"] })
  }
}

export function useCreateTestCase(projectId: string, { refresh = true }: WriteOptions = {}) {
  const doRefresh = useRefreshCases(projectId)
  return useMutation({
    mutationFn: async (input: TestCaseContent & { screen_id: string }): Promise<TestCase> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/test-cases", {
          params: { path: { project_id: projectId } },
          body: input,
        }),
      ),
    onSuccess: () => refresh && doRefresh(),
  })
}

/** Sửa nội dung; `version` là bản người dùng đang xem (khác bản trên server thì bị 409). */
export function useUpdateTestCase(
  projectId: string,
  caseId: string,
  { refresh = true }: WriteOptions = {},
) {
  const doRefresh = useRefreshCases(projectId)
  return useMutation({
    mutationFn: async (input: TestCaseContent & { version: number }): Promise<TestCase> =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/test-cases/{case_id}", {
          ...casePath(projectId, caseId),
          body: input,
        }),
      ),
    onSuccess: () => refresh && doRefresh(),
  })
}

export type TransitionInput = {
  /** Mã case lấy từ kết quả lưu (case mới tạo chưa có mã khi form mở), nên truyền lúc gọi. */
  caseId: string
  action: CaseAction
  version: number
  comment?: string
}

/** Gửi duyệt / duyệt / trả lại / ngừng dùng / khôi phục. */
export function useTransitionTestCase(projectId: string, { refresh = true }: WriteOptions = {}) {
  const doRefresh = useRefreshCases(projectId)
  return useMutation({
    mutationFn: async ({
      caseId,
      action,
      version,
      comment = "",
    }: TransitionInput): Promise<TestCase> =>
      unwrap(
        await api.POST(`/api/projects/{project_id}/test-cases/{case_id}/${action}`, {
          ...casePath(projectId, caseId),
          body: { version, comment },
        }),
      ),
    onSuccess: () => refresh && doRefresh(),
  })
}

export type ApproveItem = { case_id: string; version: number }

/** Duyệt nhiều case một lượt; server bỏ qua case lỗi và báo lại trong `skipped`. */
export function useApproveTestCases(projectId: string) {
  const doRefresh = useRefreshCases(projectId)
  return useMutation({
    mutationFn: async (items: ApproveItem[]): Promise<BatchApproveResponse> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/test-cases/approve-batch", {
          params: { path: { project_id: projectId } },
          body: { items },
        }),
      ),
    // Dù có case bị bỏ qua thì danh sách vẫn đã đổi, nên luôn làm mới.
    onSuccess: doRefresh,
  })
}


/** QA Lead/Admin đồng bộ lại issue sau khi GitHub bị lỗi. */
export function useSyncIssues(projectId: string) {
  const doRefresh = useRefreshCases(projectId)
  return useMutation({
    mutationFn: async (): Promise<SyncIssuesResult> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/test-cases/sync-issues", {
          params: { path: { project_id: projectId } },
        }),
      ),
    onSuccess: doRefresh,
  })
}

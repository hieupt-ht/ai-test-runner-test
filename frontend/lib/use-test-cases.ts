"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type { AuditEntry, TestCase, TestCaseContent, TestCaseDetail } from "@/lib/api/types"
import type { CaseAction } from "@/lib/test-cases/actions"

// Khoá cache bắt đầu bằng ["projects", projectId] nên được làm mới cùng các dữ liệu khác của dự án.
const casesKey = (projectId: string) => ["projects", projectId, "test-cases"] as const
const caseKey = (projectId: string, caseId: string) => [...casesKey(projectId), caseId] as const
const historyKey = (projectId: string, caseId: string) =>
  [...caseKey(projectId, caseId), "history"] as const

const casePath = (projectId: string, caseId: string) => ({
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

/** Sau khi ghi thì làm mới dữ liệu của dự án và "Việc của tôi" (trạng thái việc có thể đổi theo case). */
function useRefresh(projectId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
    void queryClient.invalidateQueries({ queryKey: ["me", "assignments"] })
  }
}

export function useCreateTestCase(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async (input: TestCaseContent & { screen_id: string }): Promise<TestCase> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/test-cases", {
          params: { path: { project_id: projectId } },
          body: input,
        }),
      ),
    onSuccess: refresh,
  })
}

/** Sửa nội dung; `version` là bản người dùng đang xem (khác bản trên server thì bị 409). */
export function useUpdateTestCase(projectId: string, caseId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async (input: TestCaseContent & { version: number }): Promise<TestCase> =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/test-cases/{case_id}", {
          ...casePath(projectId, caseId),
          body: input,
        }),
      ),
    onSuccess: refresh,
  })
}

export type TransitionInput = { action: CaseAction; version: number; comment?: string }

/** Gửi duyệt / duyệt / trả lại / ngừng dùng / khôi phục. */
export function useTransitionTestCase(projectId: string, caseId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async ({ action, version, comment = "" }: TransitionInput): Promise<TestCase> =>
      unwrap(
        await api.POST(`/api/projects/{project_id}/test-cases/{case_id}/${action}`, {
          ...casePath(projectId, caseId),
          body: { version, comment },
        }),
      ),
    onSuccess: refresh,
  })
}

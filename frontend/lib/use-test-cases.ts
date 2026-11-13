"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type { AuditEntry, TestCase, TestCaseDetail } from "@/lib/api/types"

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

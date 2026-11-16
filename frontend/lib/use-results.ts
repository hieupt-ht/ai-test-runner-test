"use client"

import { useMutation, useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { ensureOk, unwrap } from "@/lib/api/request"
import type { ResultItem, ResultStatus } from "@/lib/api/types"

export function useResults(projectId: string, status?: ResultStatus, screenId?: string) {
  return useQuery({
    queryKey: ["projects", projectId, "results", status ?? "all", screenId ?? "all-screens"],
    queryFn: async (): Promise<ResultItem[]> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/results", {
          params: {
            path: { project_id: projectId },
            query: {
              ...(status ? { status } : {}),
              ...(screenId ? { screen_id: screenId } : {}),
            },
          },
        }),
      ),
    enabled: Boolean(projectId),
  })
}

/**
 * Yêu cầu chạy lại một case FAIL/BLOCKED.
 * Backend chỉ để lại tín hiệu trên GitHub issue (Codex chạy ngoài app), nên không cần tải lại dữ liệu.
 */
export function useRequestRerun(projectId: string) {
  return useMutation({
    mutationFn: async (caseId: string) => {
      ensureOk(
        await api.POST("/api/projects/{project_id}/test-cases/{case_id}/request-rerun", {
          params: { path: { project_id: projectId, case_id: caseId } },
        }),
      )
    },
  })
}

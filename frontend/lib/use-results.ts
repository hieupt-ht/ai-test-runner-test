"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { ensureOk, unwrap } from "@/lib/api/request"
import type { Platform, ResultItem, ResultStatus, Run } from "@/lib/api/types"

export type ResultsFilters = {
  platform?: Platform
  runId?: string
  regressionOnly?: boolean
}

export function useResults(
  projectId: string,
  status?: ResultStatus,
  screenId?: string,
  filters: ResultsFilters = {},
) {
  return useQuery({
    queryKey: [
      "projects",
      projectId,
      "results",
      status ?? "all",
      screenId ?? "all-screens",
      filters.platform ?? "all-platforms",
      filters.runId ?? "latest",
      filters.regressionOnly ?? false,
    ],
    queryFn: async (): Promise<ResultItem[]> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/results", {
          params: {
            path: { project_id: projectId },
            query: {
              ...(status ? { status } : {}),
              ...(screenId ? { screen_id: screenId } : {}),
              ...(filters.platform ? { platform: filters.platform } : {}),
              ...(filters.runId ? { run_id: filters.runId } : {}),
              ...(filters.regressionOnly ? { regression_only: true } : {}),
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

/** Các lần chạy regression còn đang mở (để hiện nút "Kết thúc"). */
export function useOpenRegressionRuns(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "regression-runs"],
    queryFn: async (): Promise<Run[]> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/regression-runs", {
          params: { path: { project_id: projectId } },
        }),
      ),
    enabled: Boolean(projectId),
  })
}

/** Sau khi tạo/kết thúc run: tải lại danh sách run mở và kết quả. */
function useRefreshRegression(projectId: string) {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
}

export function useCreateRegressionRun(projectId: string) {
  const refresh = useRefreshRegression(projectId)
  return useMutation({
    mutationFn: async (body: { build_version: string }): Promise<Run> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/regression-runs", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: refresh,
  })
}

export function useFinishRegressionRun(projectId: string) {
  const refresh = useRefreshRegression(projectId)
  return useMutation({
    mutationFn: async (runId: string): Promise<Run> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/regression-runs/{run_id}/finish", {
          params: { path: { project_id: projectId, run_id: runId } },
        }),
      ),
    onSuccess: refresh,
  })
}

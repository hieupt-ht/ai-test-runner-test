"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type { PreviewResponse, RunDetail, RunScope, RunStatus, RunView } from "@/lib/api/types"
import { isRunActive } from "@/lib/runs/summary"

// Mỗi lượt làm mới là vài lượt đọc Google Sheets (hạn mức ~60 lượt/phút cho cả worker), nên không quá dày.
const POLL_MS = 5000

// Khoá cache bắt đầu bằng ["projects", projectId] nên được làm mới cùng dữ liệu khác của dự án.
const runsKey = (projectId: string) => ["projects", projectId, "runs"] as const
const runKey = (projectId: string, runId: string) => [...runsKey(projectId), runId] as const

/** Run còn QUEUED/RUNNING thì làm mới mỗi 5 giây; xong hoặc chưa có dữ liệu thì dừng. */
export function runPollInterval(run: { status: RunStatus } | undefined): number | false {
  return run && isRunActive(run.status) ? POLL_MS : false
}

export function useRuns(projectId: string) {
  return useQuery({
    queryKey: runsKey(projectId),
    queryFn: async (): Promise<RunView[]> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/runs", {
          params: { path: { project_id: projectId } },
        }),
      ),
    refetchInterval: (query) =>
      query.state.data?.some((run) => isRunActive(run.status)) ? POLL_MS : false,
  })
}

export function useRun(projectId: string, runId: string | undefined) {
  return useQuery({
    queryKey: runKey(projectId, runId ?? ""),
    enabled: Boolean(runId),
    queryFn: async (): Promise<RunDetail> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/runs/{run_id}", {
          params: { path: { project_id: projectId, run_id: runId ?? "" } },
        }),
      ),
    refetchInterval: (query) => runPollInterval(query.state.data),
  })
}

/** Số case sẽ chạy với phạm vi này (hiện trước khi bấm Chạy). */
export function usePreviewRun(projectId: string, scope: RunScope) {
  return useQuery({
    queryKey: [...runsKey(projectId), "preview", scope] as const,
    queryFn: async (): Promise<PreviewResponse> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/runs/preview", {
          params: { path: { project_id: projectId } },
          body: scope,
        }),
      ),
  })
}

export function useStartRun(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (scope: RunScope): Promise<RunView> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/runs", {
          params: { path: { project_id: projectId } },
          body: { scope },
        }),
      ),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: runsKey(projectId) }),
  })
}

export function useCancelRun(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (runId: string): Promise<RunView> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/runs/{run_id}/cancel", {
          params: { path: { project_id: projectId, run_id: runId } },
        }),
      ),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: runsKey(projectId) }),
  })
}

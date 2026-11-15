"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
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

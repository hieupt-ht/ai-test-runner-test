"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type { ManualResultRequest, ManualResultResponse } from "@/lib/api/types"

/** Tester gửi kết quả chạy tay của một case; xong thì làm mới case, kết quả và việc được giao. */
export function useSubmitManualResult(projectId: string, caseId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: ManualResultRequest): Promise<ManualResultResponse> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/test-cases/{case_id}/manual-results", {
          params: { path: { project_id: projectId, case_id: caseId } },
          body,
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
      void queryClient.invalidateQueries({ queryKey: ["me", "assignments"] })
    },
  })
}

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { ensureOk, unwrap } from "@/lib/api/request"
import type { Module, ModuleAssignment, ModuleView } from "@/lib/api/types"

const modulesKey = (projectId: string) => ["projects", projectId, "modules"] as const
const MY_WORK_KEY = ["me", "assignments"] as const

const path = (projectId: string) => ({ params: { path: { project_id: projectId } } })

/** Module đổi thì việc giao màn hình cũng đổi, nên làm mới cả dự án lẫn "Việc của tôi". */
function useRefresh(projectId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
    void queryClient.invalidateQueries({ queryKey: MY_WORK_KEY })
  }
}

export function useModules(projectId: string) {
  return useQuery({
    queryKey: modulesKey(projectId),
    queryFn: async (): Promise<ModuleView[]> =>
      unwrap(await api.GET("/api/projects/{project_id}/modules", path(projectId))),
  })
}

export type ModuleInput = { name: string; description: string }

export function useSaveModule(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async ({ id, ...body }: ModuleInput & { id?: string }): Promise<Module> =>
      id
        ? unwrap(
            await api.PATCH("/api/projects/{project_id}/modules/{module_id}", {
              params: { path: { project_id: projectId, module_id: id } },
              body,
            }),
          )
        : unwrap(await api.POST("/api/projects/{project_id}/modules", { ...path(projectId), body })),
    onSuccess: refresh,
  })
}

export function useDeleteModule(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async (moduleId: string) =>
      ensureOk(
        await api.DELETE("/api/projects/{project_id}/modules/{module_id}", {
          params: { path: { project_id: projectId, module_id: moduleId } },
        }),
      ),
    onSuccess: refresh,
  })
}

export type AssignModuleInput = { moduleId: string; emails: string[]; deadline: string }

export function useAssignModule(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async ({ moduleId, emails, deadline }: AssignModuleInput): Promise<ModuleAssignment[]> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/modules/{module_id}/workers", {
          params: { path: { project_id: projectId, module_id: moduleId } },
          body: { emails, deadline },
        }),
      ),
    onSuccess: refresh,
  })
}

export function useUnassignModule(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async ({ moduleId, workerId }: { moduleId: string; workerId: string }) =>
      unwrap(
        await api.DELETE("/api/projects/{project_id}/modules/{module_id}/workers/{worker_id}", {
          params: { path: { project_id: projectId, module_id: moduleId, worker_id: workerId } },
        }),
      ),
    onSuccess: refresh,
  })
}

export function useChangeModuleDeadline(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async ({
      moduleId,
      workerId,
      deadline,
    }: {
      moduleId: string
      workerId: string
      deadline: string
    }): Promise<ModuleAssignment> =>
      unwrap(
        await api.PATCH("/api/projects/{project_id}/modules/{module_id}/workers/{worker_id}", {
          params: { path: { project_id: projectId, module_id: moduleId, worker_id: workerId } },
          body: { deadline },
        }),
      ),
    onSuccess: refresh,
  })
}

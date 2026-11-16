"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { ensureOk, unwrap } from "@/lib/api/request"
import type { Assignment, MemberView, MyAssignment, Screen } from "@/lib/api/types"

// ----- Khoá cache của TanStack Query -----

const screensKey = (projectId: string) => ["projects", projectId, "screens"] as const
const assignmentsKey = (projectId: string) => ["projects", projectId, "assignments"] as const
const membersKey = (projectId: string) => ["projects", projectId, "members"] as const
const MY_WORK_KEY = ["me", "assignments"] as const

const path = (projectId: string) => ({ params: { path: { project_id: projectId } } })

/** Sau khi ghi thì làm mới dữ liệu liên quan (giao việc ảnh hưởng cả "Việc của tôi"). */
function useRefresh(projectId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
    void queryClient.invalidateQueries({ queryKey: MY_WORK_KEY })
  }
}

// ----- Màn hình -----

export type ScreenInput = { name: string; description: string; route: string; code_paths: string[] }

export function useScreens(projectId: string) {
  return useQuery({
    queryKey: screensKey(projectId),
    queryFn: async (): Promise<Screen[]> =>
      unwrap(await api.GET("/api/projects/{project_id}/screens", path(projectId))),
  })
}

export function useSaveScreen(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async ({ id, ...body }: ScreenInput & { id?: string }): Promise<Screen> =>
      id
        ? unwrap(
            await api.PATCH("/api/projects/{project_id}/screens/{screen_id}", {
              params: { path: { project_id: projectId, screen_id: id } },
              body,
            }),
          )
        : unwrap(await api.POST("/api/projects/{project_id}/screens", { ...path(projectId), body })),
    onSuccess: refresh,
  })
}

export function useDeleteScreen(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async (screenId: string) =>
      ensureOk(
        await api.DELETE("/api/projects/{project_id}/screens/{screen_id}", {
          params: { path: { project_id: projectId, screen_id: screenId } },
        }),
      ),
    onSuccess: refresh,
  })
}

// ----- Giao việc -----

export function useAssignments(projectId: string) {
  return useQuery({
    queryKey: assignmentsKey(projectId),
    queryFn: async (): Promise<Assignment[]> =>
      unwrap(await api.GET("/api/projects/{project_id}/assignments", path(projectId))),
  })
}

export type AssignInput = { screen_id: string; assignee_emails: string[]; deadline: string }

export function useAssign(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async (body: AssignInput): Promise<Assignment[]> =>
      unwrap(await api.POST("/api/projects/{project_id}/assignments", { ...path(projectId), body })),
    onSuccess: refresh,
  })
}

export function useUnassign(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async (assignmentId: string) =>
      ensureOk(
        await api.DELETE("/api/projects/{project_id}/assignments/{assignment_id}", {
          params: { path: { project_id: projectId, assignment_id: assignmentId } },
        }),
      ),
    onSuccess: refresh,
  })
}

// ----- Thành viên -----

export function useMembers(projectId: string) {
  return useQuery({
    queryKey: membersKey(projectId),
    queryFn: async (): Promise<MemberView[]> =>
      unwrap(await api.GET("/api/projects/{project_id}/members", path(projectId))),
  })
}

export function useAddMember(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async (email: string): Promise<MemberView> =>
      unwrap(
        await api.POST("/api/projects/{project_id}/members", {
          ...path(projectId),
          body: { email },
        }),
      ),
    onSuccess: refresh,
  })
}

export function useRemoveMember(projectId: string) {
  const refresh = useRefresh(projectId)
  return useMutation({
    mutationFn: async (email: string) =>
      ensureOk(
        await api.DELETE("/api/projects/{project_id}/members/{email}", {
          params: { path: { project_id: projectId, email } },
        }),
      ),
    onSuccess: refresh,
  })
}

// ----- Việc của tôi -----

export function useMyAssignments(enabled = true) {
  return useQuery({
    queryKey: MY_WORK_KEY,
    queryFn: async (): Promise<MyAssignment[]> => unwrap(await api.GET("/api/me/assignments")),
    enabled,
  })
}

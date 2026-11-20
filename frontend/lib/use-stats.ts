"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type { Leaderboard, MyDashboard, MyPet, Period, ProjectStats } from "@/lib/api/types"

// Key bắt đầu bằng ["projects", projectId] nên khi ghi case/kết quả (làm mới cả project)
// thì số liệu và bảng xếp hạng cũng được tải lại.

export function useProjectStats(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId, "stats"],
    queryFn: async (): Promise<ProjectStats> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/stats", {
          params: { path: { project_id: projectId } },
        }),
      ),
  })
}

export function useLeaderboard(projectId: string, period: Period) {
  return useQuery({
    queryKey: ["projects", projectId, "leaderboard", period],
    queryFn: async (): Promise<Leaderboard> =>
      unwrap(
        await api.GET("/api/projects/{project_id}/leaderboard", {
          params: { path: { project_id: projectId }, query: { period } },
        }),
      ),
  })
}

export function useMyDashboard() {
  return useQuery({
    queryKey: ["me", "dashboard"],
    queryFn: async (): Promise<MyDashboard> => unwrap(await api.GET("/api/me/dashboard")),
  })
}

export function useMyPet() {
  return useQuery({
    queryKey: ["me", "pet"],
    queryFn: async (): Promise<MyPet> => unwrap(await api.GET("/api/me/pet")),
  })
}

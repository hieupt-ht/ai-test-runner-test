"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type { Project, ProjectDetail, RepoInfo } from "@/lib/api/types"

export const PROJECTS_KEY = ["projects"] as const

export function projectKey(projectId: string) {
  return ["projects", projectId] as const
}

export function useProjects(enabled = true) {
  return useQuery({
    queryKey: PROJECTS_KEY,
    queryFn: async (): Promise<Project[]> => unwrap(await api.GET("/api/projects")),
    enabled,
  })
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: projectKey(projectId),
    queryFn: async (): Promise<ProjectDetail> =>
      unwrap(
        await api.GET("/api/projects/{project_id}", {
          params: { path: { project_id: projectId } },
        }),
      ),
    retry: false,
  })
}

export function useServiceAccountEmail(enabled: boolean) {
  return useQuery({
    queryKey: ["service-account"],
    queryFn: async () => unwrap(await api.GET("/api/settings/service-account")).email,
    enabled,
    staleTime: Infinity,
  })
}

export function useGithubRepositories(enabled: boolean) {
  return useQuery({
    queryKey: ["github", "repositories"],
    queryFn: async (): Promise<RepoInfo[]> => unwrap(await api.GET("/api/github/repositories")),
    enabled,
    retry: false,
  })
}

export function useGithubBranches(repoFullName: string | null) {
  const [owner = "", repo = ""] = (repoFullName ?? "").split("/")
  return useQuery({
    queryKey: ["github", "branches", repoFullName],
    queryFn: async (): Promise<string[]> =>
      unwrap(
        await api.GET("/api/github/repositories/{owner}/{repo}/branches", {
          params: { path: { owner, repo } },
        }),
      ),
    enabled: Boolean(repoFullName),
    retry: false,
  })
}

export type CreateProjectInput = {
  name: string
  repo_full_name: string
  branch: string
  staging_url: string
  spreadsheet: string
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: CreateProjectInput): Promise<Project> =>
      unwrap(await api.POST("/api/projects", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROJECTS_KEY }),
  })
}

export type UpdateProjectInput = {
  name?: string
  branch?: string
  staging_url?: string
  archived?: boolean
  android_app_id?: string
  ios_bundle_id?: string
  require_review?: boolean
}

export function useUpdateProject(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: UpdateProjectInput): Promise<Project> =>
      unwrap(
        await api.PATCH("/api/projects/{project_id}", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    // Làm mới cả danh sách lẫn chi tiết dự án
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROJECTS_KEY }),
  })
}

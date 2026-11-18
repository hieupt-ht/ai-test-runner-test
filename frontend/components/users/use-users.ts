"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api, ApiError, errorMessage } from "@/lib/api/client"
import type { Role, User } from "@/lib/api/types"

const USERS_QUERY_KEY = ["users"] as const
const FALLBACK_ERROR = "Có lỗi xảy ra, vui lòng thử lại."

export function useUsers({ enabled }: { enabled: boolean }) {
  return useQuery({
    queryKey: USERS_QUERY_KEY,
    queryFn: async (): Promise<User[]> => {
      const { data, error, response } = await api.GET("/api/users")
      if (data === undefined) {
        throw new ApiError(response.status, errorMessage(error, FALLBACK_ERROR))
      }
      return data
    },
    enabled,
    retry: false,
  })
}

export type CreateUserInput = { email: string; name: string; role: Role; password: string }
export type UpdateUserInput = { email: string; name?: string; role?: Role; active?: boolean }

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (input: CreateUserInput): Promise<User> => {
      const { data, error, response } = await api.POST("/api/users", { body: input })
      if (data === undefined) {
        throw new ApiError(response.status, errorMessage(error, FALLBACK_ERROR))
      }
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY }),
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ email, ...changes }: UpdateUserInput): Promise<User> => {
      const { data, error, response } = await api.PATCH("/api/users/{email}", {
        params: { path: { email } },
        body: changes,
      })
      if (data === undefined) {
        throw new ApiError(response.status, errorMessage(error, FALLBACK_ERROR))
      }
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY }),
  })
}

export function useResetPassword() {
  return useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }): Promise<void> => {
      const { error, response } = await api.POST("/api/users/{email}/reset-password", {
        params: { path: { email } },
        body: { password },
      })
      if (!response.ok) {
        throw new ApiError(response.status, errorMessage(error, FALLBACK_ERROR))
      }
    },
  })
}

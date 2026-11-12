"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import type { User } from "@/lib/api/types"

export const ME_QUERY_KEY = ["me"] as const

/** Người dùng đang đăng nhập. `user` là null khi chưa đăng nhập. */
export function useMe(): { user: User | null; isLoading: boolean } {
  const query = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/me")
      if (response.status === 401) return null
      return data ?? null
    },
    retry: false,
    staleTime: 60_000,
  })
  return { user: query.data ?? null, isLoading: query.isLoading }
}

"use client"

import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type { OverviewSummary } from "@/lib/api/types"

export function useOverview(enabled: boolean) {
  return useQuery({
    queryKey: ["me", "overview"],
    queryFn: async (): Promise<OverviewSummary> => unwrap(await api.GET("/api/me/overview")),
    enabled,
  })
}

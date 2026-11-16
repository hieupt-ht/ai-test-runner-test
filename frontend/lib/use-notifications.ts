"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api/client"
import { ensureOk, unwrap } from "@/lib/api/request"
import type { components } from "@/lib/api/schema"

export type Notification = components["schemas"]["Notification"]
export type NotificationList = components["schemas"]["NotificationList"]

const notificationsKey = ["notifications"] as const

export function useNotifications() {
  return useQuery({
    queryKey: notificationsKey,
    queryFn: async (): Promise<NotificationList> => unwrap(await api.GET("/api/notifications")),
    refetchInterval: 45_000,
    refetchIntervalInBackground: false,
  })
}

export function useMarkRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (notificationId: string) => {
      ensureOk(await api.POST("/api/notifications/{notification_id}/read", {
        params: { path: { notification_id: notificationId } },
      }))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsKey }),
  })
}

export function useMarkAllRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      ensureOk(await api.POST("/api/notifications/read-all"))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsKey }),
  })
}

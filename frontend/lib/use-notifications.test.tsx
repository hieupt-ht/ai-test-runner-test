import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api/client"
import { useMarkAllRead, useMarkRead, useNotifications } from "@/lib/use-notifications"

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn(), POST: vi.fn() } }))

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

describe("notification hooks", () => {
  beforeEach(() => vi.clearAllMocks())

  it("lấy thông báo và chỉ làm mới định kỳ khi tab đang hiện", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: { items: [], unread: 0 } } as never)
    const { client, wrapper } = setup()
    const { result } = renderHook(useNotifications, { wrapper })

    await waitFor(() => expect(result.current.data).toEqual({ items: [], unread: 0 }))
    expect(api.GET).toHaveBeenCalledWith("/api/notifications")
    const query = client.getQueryCache().find({ queryKey: ["notifications"] })
    expect(query?.options).toMatchObject({
      refetchInterval: 45_000,
      refetchIntervalInBackground: false,
    })
  })

  it("đánh dấu một thông báo và làm mới danh sách", async () => {
    vi.mocked(api.POST).mockResolvedValue({ response: { ok: true, status: 204 } } as never)
    const { client, wrapper } = setup()
    const invalidate = vi.spyOn(client, "invalidateQueries")
    const { result } = renderHook(useMarkRead, { wrapper })

    await act(() => result.current.mutateAsync("n1"))
    expect(api.POST).toHaveBeenCalledWith("/api/notifications/{notification_id}/read", {
      params: { path: { notification_id: "n1" } },
    })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["notifications"] })
  })

  it("đánh dấu toàn bộ và làm mới danh sách", async () => {
    vi.mocked(api.POST).mockResolvedValue({ response: { ok: true, status: 204 } } as never)
    const { client, wrapper } = setup()
    const invalidate = vi.spyOn(client, "invalidateQueries")
    const { result } = renderHook(useMarkAllRead, { wrapper })

    await act(() => result.current.mutateAsync())
    expect(api.POST).toHaveBeenCalledWith("/api/notifications/read-all")
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["notifications"] })
  })
})

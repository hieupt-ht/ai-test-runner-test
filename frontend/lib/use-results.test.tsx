import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api/client"
import { useResults } from "@/lib/use-results"

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }))

describe("useResults", () => {
  it("gọi API với mã dự án và bộ lọc trạng thái", async () => {
    vi.mocked(api.GET).mockResolvedValue({ data: [] } as never)
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        {children}
      </QueryClientProvider>
    )
    const { result } = renderHook(() => useResults("p1", "FAIL", "SC-login"), { wrapper })

    await act(async () => {
      await waitFor(() => expect(result.current.data).toEqual([]))
    })
    expect(api.GET).toHaveBeenCalledWith("/api/projects/{project_id}/results", {
      params: {
        path: { project_id: "p1" },
        query: { status: "FAIL", screen_id: "SC-login" },
      },
    })
  })
})

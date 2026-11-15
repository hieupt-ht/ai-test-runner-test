import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api/client"
import { useRequestRerun, useResults } from "@/lib/use-results"

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: { GET: vi.fn(), POST: vi.fn() },
}))

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
  return Wrapper
}

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

  it("yêu cầu chạy lại gọi đúng endpoint với mã dự án và mã case", async () => {
    vi.mocked(api.POST).mockResolvedValue({ response: { ok: true } } as never)
    const { result } = renderHook(() => useRequestRerun("p1"), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.mutateAsync("TC-000001")
    })

    expect(api.POST).toHaveBeenCalledWith(
      "/api/projects/{project_id}/test-cases/{case_id}/request-rerun",
      { params: { path: { project_id: "p1", case_id: "TC-000001" } } },
    )
  })

  it("yêu cầu chạy lại ném lỗi kèm câu báo của API khi thất bại", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      response: { ok: false, status: 503 },
      error: { detail: "Chưa cấu hình GitHub" },
    } as never)
    const { result } = renderHook(() => useRequestRerun("p1"), { wrapper: makeWrapper() })

    await act(async () => {
      await expect(result.current.mutateAsync("TC-000001")).rejects.toThrow("Chưa cấu hình GitHub")
    })
  })
})

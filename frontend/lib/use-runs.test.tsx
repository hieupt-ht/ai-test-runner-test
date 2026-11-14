import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api/client"
import { runPollInterval, useRun, useStartRun } from "@/lib/use-runs"

vi.mock("@/lib/api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
  ApiError: class extends Error {},
  errorMessage: () => "",
}))

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe("runPollInterval", () => {
  it("làm mới mỗi 5 giây khi run còn QUEUED/RUNNING, dừng khi xong hoặc chưa có dữ liệu", () => {
    expect(runPollInterval({ status: "QUEUED" })).toBe(5000)
    expect(runPollInterval({ status: "RUNNING" })).toBe(5000)
    expect(runPollInterval({ status: "COMPLETED" })).toBe(false)
    expect(runPollInterval({ status: "CANCELLED" })).toBe(false)
    expect(runPollInterval(undefined)).toBe(false)
  })
})

describe("useRun", () => {
  it("gọi đúng đường dẫn với mã dự án và mã run", async () => {
    vi.mocked(api.GET).mockResolvedValue({
      data: { id: "RUN-0001", status: "COMPLETED", results: [] },
      response: { ok: true, status: 200 },
    } as never)

    const { result } = renderHook(() => useRun("P1", "RUN-0001"), { wrapper })

    await waitFor(() => expect(result.current.data?.id).toBe("RUN-0001"))
    expect(api.GET).toHaveBeenCalledWith("/api/projects/{project_id}/runs/{run_id}", {
      params: { path: { project_id: "P1", run_id: "RUN-0001" } },
    })
  })
})

describe("useStartRun", () => {
  it("gửi phạm vi lên API tạo run", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "RUN-0002" },
      response: { ok: true, status: 201 },
    } as never)
    const { result } = renderHook(() => useStartRun("P1"), { wrapper })
    const scope = { screen_ids: ["SC-0001"], priorities: [], severities: [] }

    await act(() => result.current.mutateAsync(scope))

    expect(api.POST).toHaveBeenCalledWith("/api/projects/{project_id}/runs", {
      params: { path: { project_id: "P1" } },
      body: { scope },
    })
  })
})

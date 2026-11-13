import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api/client"
import { useTransitionTestCase } from "@/lib/use-test-cases"

vi.mock("@/lib/api/client", () => ({
  api: { POST: vi.fn() },
  ApiError: class extends Error {},
  errorMessage: () => "",
}))

describe("useTransitionTestCase", () => {
  it("gọi đúng mã case truyền lúc gọi (case vừa tạo xong rồi gửi duyệt)", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { id: "TC-000009", version: 2 },
      response: { ok: true, status: 200 },
    } as never)
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useTransitionTestCase("P1", { refresh: false }), { wrapper })

    await act(() => result.current.mutateAsync({ caseId: "TC-000009", action: "submit", version: 1 }))

    expect(api.POST).toHaveBeenCalledWith(
      "/api/projects/{project_id}/test-cases/{case_id}/submit",
      {
        params: { path: { project_id: "P1", case_id: "TC-000009" } },
        body: { version: 1, comment: "" },
      },
    )
  })
})

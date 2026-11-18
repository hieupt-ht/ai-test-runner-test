import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api/client"
import type { ManualResultRequest } from "@/lib/api/types"
import { useSubmitManualResult } from "@/lib/use-manual-result"

vi.mock("@/lib/api/client", () => ({
  api: { POST: vi.fn() },
  ApiError: class extends Error {},
  errorMessage: () => "",
}))

const BODY: ManualResultRequest = {
  status: "PASS",
  step_results: [{ step_no: 1, status: "PASS", actual: "" }],
  actual_result: "",
  reason: "",
  environment: "Chrome 130",
  build_version: "",
  assignee: "",
  version: 3,
}

describe("useSubmitManualResult", () => {
  it("gửi kết quả vào đúng case rồi làm mới dữ liệu dự án và việc của tôi", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { run_id: "RUN-0001", case: { id: "TC-000001" } },
      response: { ok: true, status: 201 },
    } as never)
    const client = new QueryClient()
    const invalidate = vi.spyOn(client, "invalidateQueries")
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useSubmitManualResult("P1", "TC-000001"), { wrapper })

    const reply = await act(() => result.current.mutateAsync(BODY))

    expect(api.POST).toHaveBeenCalledWith(
      "/api/projects/{project_id}/test-cases/{case_id}/manual-results",
      { params: { path: { project_id: "P1", case_id: "TC-000001" } }, body: BODY },
    )
    expect(reply.run_id).toBe("RUN-0001")
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects", "P1"] })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["me", "assignments"] })
  })
})

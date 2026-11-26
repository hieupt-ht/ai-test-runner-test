import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"

import { api } from "@/lib/api/client"
import {
  useAssignModule,
  useChangeModuleDeadline,
  useDeleteModule,
  useModules,
  useSaveModule,
  useUnassignModule,
} from "@/lib/use-modules"

vi.mock("@/lib/api/client", () => ({
  api: { POST: vi.fn(), GET: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
  ApiError: class extends Error {},
  errorMessage: () => "",
}))

const ok = (data: unknown) => ({ data, response: { ok: true, status: 200 } }) as never

function setup() {
  const client = new QueryClient()
  const invalidate = vi.spyOn(client, "invalidateQueries")
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { invalidate, wrapper }
}

function expectRefreshed(invalidate: ReturnType<typeof vi.spyOn>) {
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects", "P1"] })
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["me", "assignments"] })
}

describe("useModules", () => {
  it("gọi đúng URL danh sách module", async () => {
    vi.mocked(api.GET).mockResolvedValue(ok([]))
    const { wrapper } = setup()
    const { result } = renderHook(() => useModules("P1"), { wrapper })

    await act(async () => result.current.refetch())

    expect(api.GET).toHaveBeenCalledWith("/api/projects/{project_id}/modules", {
      params: { path: { project_id: "P1" } },
    })
  })
})

describe("useSaveModule", () => {
  it("không có id thì tạo mới (POST)", async () => {
    vi.mocked(api.POST).mockResolvedValue(ok({ id: "MD-0001" }))
    const { wrapper, invalidate } = setup()
    const { result } = renderHook(() => useSaveModule("P1"), { wrapper })

    await act(() => result.current.mutateAsync({ name: "Tài khoản", description: "" }))

    expect(api.POST).toHaveBeenCalledWith("/api/projects/{project_id}/modules", {
      params: { path: { project_id: "P1" } },
      body: { name: "Tài khoản", description: "" },
    })
    expectRefreshed(invalidate)
  })

  it("có id thì sửa (PATCH)", async () => {
    vi.mocked(api.PATCH).mockResolvedValue(ok({ id: "MD-0001" }))
    const { wrapper } = setup()
    const { result } = renderHook(() => useSaveModule("P1"), { wrapper })

    await act(() => result.current.mutateAsync({ id: "MD-0001", name: "Mới", description: "x" }))

    expect(api.PATCH).toHaveBeenCalledWith("/api/projects/{project_id}/modules/{module_id}", {
      params: { path: { project_id: "P1", module_id: "MD-0001" } },
      body: { name: "Mới", description: "x" },
    })
  })
})

describe("useDeleteModule", () => {
  it("xoá đúng module rồi làm mới", async () => {
    vi.mocked(api.DELETE).mockResolvedValue({ response: { ok: true, status: 204 } } as never)
    const { wrapper, invalidate } = setup()
    const { result } = renderHook(() => useDeleteModule("P1"), { wrapper })

    await act(() => result.current.mutateAsync("MD-0001"))

    expect(api.DELETE).toHaveBeenCalledWith("/api/projects/{project_id}/modules/{module_id}", {
      params: { path: { project_id: "P1", module_id: "MD-0001" } },
    })
    expectRefreshed(invalidate)
  })
})

describe("giao / bỏ nhận / đổi hạn", () => {
  it("useAssignModule gửi emails và deadline tới /workers", async () => {
    vi.mocked(api.POST).mockResolvedValue(ok([]))
    const { wrapper, invalidate } = setup()
    const { result } = renderHook(() => useAssignModule("P1"), { wrapper })

    await act(() =>
      result.current.mutateAsync({ moduleId: "MD-0001", emails: ["a@x.com"], deadline: "2026-12-01" }),
    )

    expect(api.POST).toHaveBeenLastCalledWith("/api/projects/{project_id}/modules/{module_id}/workers", {
      params: { path: { project_id: "P1", module_id: "MD-0001" } },
      body: { emails: ["a@x.com"], deadline: "2026-12-01" },
    })
    expectRefreshed(invalidate)
  })

  it("useUnassignModule gọi DELETE đúng worker và trả số việc đã xoá", async () => {
    vi.mocked(api.DELETE).mockResolvedValue(ok({ removed_screen_assignments: 3 }))
    const { wrapper, invalidate } = setup()
    const { result } = renderHook(() => useUnassignModule("P1"), { wrapper })

    const data = await act(() => result.current.mutateAsync({ moduleId: "MD-0001", workerId: "MA-0001" }))

    expect(data).toEqual({ removed_screen_assignments: 3 })
    expect(api.DELETE).toHaveBeenLastCalledWith(
      "/api/projects/{project_id}/modules/{module_id}/workers/{worker_id}",
      { params: { path: { project_id: "P1", module_id: "MD-0001", worker_id: "MA-0001" } } },
    )
    expectRefreshed(invalidate)
  })

  it("useChangeModuleDeadline gọi PATCH với hạn mới", async () => {
    vi.mocked(api.PATCH).mockResolvedValue(ok({ id: "MA-0001" }))
    const { wrapper } = setup()
    const { result } = renderHook(() => useChangeModuleDeadline("P1"), { wrapper })

    await act(() =>
      result.current.mutateAsync({ moduleId: "MD-0001", workerId: "MA-0001", deadline: "2026-12-09" }),
    )

    expect(api.PATCH).toHaveBeenLastCalledWith(
      "/api/projects/{project_id}/modules/{module_id}/workers/{worker_id}",
      {
        params: { path: { project_id: "P1", module_id: "MD-0001", worker_id: "MA-0001" } },
        body: { deadline: "2026-12-09" },
      },
    )
  })
})

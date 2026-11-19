import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api/client"
import { templateUrl, useImportCases, usePreviewImport } from "@/lib/use-case-import"

const file = new File(["x"], "cases.xlsx")

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
}

function setup() {
  const queryClient = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

/** Chờ một lời hứa bị từ chối và trả về lỗi đó. */
async function rejectionOf(promise: Promise<unknown>) {
  let caught: ApiError | undefined
  await act(async () => {
    await promise.catch((e) => {
      caught = e
    })
  })
  return caught as ApiError
}

afterEach(() => vi.unstubAllGlobals())

describe("templateUrl", () => {
  it("trỏ đúng đường dẫn tải file mẫu", () => {
    expect(templateUrl("P 1")).toBe("/api/projects/P%201/test-cases/import/template")
  })
})

describe("usePreviewImport", () => {
  it("gửi FormData có trường file tới đúng URL xem trước", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { cases: [], errors: [] }))
    vi.stubGlobal("fetch", fetchMock)
    const { wrapper } = setup()
    const { result } = renderHook(() => usePreviewImport("P1"), { wrapper })

    await act(() => result.current.mutateAsync(file))

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/projects/P1/test-cases/import/preview")
    expect(init.method).toBe("POST")
    expect(init.credentials).toBe("same-origin")
    expect((init.body as FormData).get("file")).toBe(file)
  })
})

describe("useImportCases", () => {
  it("201 thì làm mới cache của dự án", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(201, { created: ["TC-1"] })))
    const { queryClient, wrapper } = setup()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    const { result } = renderHook(() => useImportCases("P1"), { wrapper })

    const created = await act(() => result.current.mutateAsync(file))

    expect(created).toEqual({ created: ["TC-1"] })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects", "P1"] })
  })

  it("503 thì ApiError.message là câu của backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(503, { detail: "Không kết nối được Google" })))
    const { wrapper } = setup()
    const { result } = renderHook(() => useImportCases("P1"), { wrapper })

    const error = await rejectionOf(result.current.mutateAsync(file))

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(503)
    expect(error.message).toBe("Không kết nối được Google")
  })

  it("422 thì giữ nguyên danh sách lỗi trong ApiError.body", async () => {
    const body = { detail: "File còn lỗi", errors: [{ row: 2, message: "a" }, { row: 3, message: "b" }] }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(422, body)))
    const { wrapper } = setup()
    const { result } = renderHook(() => useImportCases("P1"), { wrapper })

    const error = await rejectionOf(result.current.mutateAsync(file))

    expect(error.status).toBe(422)
    expect((error.body as typeof body).errors).toHaveLength(2)
  })
})

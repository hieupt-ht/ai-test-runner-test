import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { OpenRegressionRuns, RegressionDialog } from "@/components/results/regression-dialog"
import type { Run } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const createRun = vi.fn()
const finishRun = vi.fn()
let openRuns: Run[] = []

vi.mock("@/lib/use-results", () => ({
  useCreateRegressionRun: () => ({ mutateAsync: createRun, isPending: false }),
  useFinishRegressionRun: () => ({ mutateAsync: finishRun, isPending: false }),
  useOpenRegressionRuns: () => ({ data: openRuns }),
}))

const runningRun = {
  id: "RUN-0007",
  triggered_by: "lead@x.com",
  scope: { regression_only: true, case_ids: ["TC-1", "TC-2"], screen_ids: [], priorities: [], severities: [] },
  branch: "main",
  commit_sha: "",
  status: "RUNNING",
  started_at: "2026-11-17T01:00:00Z",
  finished_at: null,
  total: 2,
  passed: 0,
  failed: 0,
  tokens_used: 0,
  build_version: "1.4.2",
} satisfies Run

function wrap(node: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      {node}
    </NextIntlClientProvider>,
  )
}

describe("RegressionDialog", () => {
  afterEach(() => {
    cleanup()
    createRun.mockReset()
    finishRun.mockReset()
    openRuns = []
  })

  function open(onCreated = vi.fn()) {
    wrap(<RegressionDialog projectId="P1" onCreated={onCreated} />)
    fireEvent.click(screen.getByRole("button", { name: "Chạy bộ regression" }))
    return onCreated
  }

  it("khoá nút gửi khi chưa nhập bản build", () => {
    open()
    expect(screen.getByRole("button", { name: "Tạo lần chạy" })).toBeDisabled()
    fireEvent.change(screen.getByLabelText("Bản build"), { target: { value: "   " } })
    expect(screen.getByRole("button", { name: "Tạo lần chạy" })).toBeDisabled()
  })

  it("gửi đúng build_version và báo run mới cho trang để chọn sẵn bộ lọc", async () => {
    createRun.mockResolvedValue(runningRun)
    const onCreated = open()
    fireEvent.change(screen.getByLabelText("Bản build"), { target: { value: " 1.4.2 " } })
    fireEvent.click(screen.getByRole("button", { name: "Tạo lần chạy" }))
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(runningRun))
    expect(createRun).toHaveBeenCalledWith({ build_version: "1.4.2" })
  })
})

describe("OpenRegressionRuns", () => {
  afterEach(() => {
    cleanup()
    finishRun.mockReset()
    openRuns = []
  })

  it("QA Lead thấy nút Kết thúc cho run đang chạy và bấm được", async () => {
    openRuns = [runningRun]
    finishRun.mockResolvedValue({ ...runningRun, status: "COMPLETED" })
    wrap(<OpenRegressionRuns projectId="P1" canManage />)
    expect(screen.getByText(/RUN-0007/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Kết thúc RUN-0007" }))
    await waitFor(() => expect(finishRun).toHaveBeenCalledWith("RUN-0007"))
  })

  it("người không có quyền không thấy nút Kết thúc", () => {
    openRuns = [runningRun]
    wrap(<OpenRegressionRuns projectId="P1" canManage={false} />)
    expect(screen.queryByRole("button", { name: /Kết thúc/ })).toBeNull()
  })

  it("không có run đang chạy thì không hiện gì", () => {
    const { container } = wrap(<OpenRegressionRuns projectId="P1" canManage />)
    expect(container).toBeEmptyDOMElement()
  })
})

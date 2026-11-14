import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RunDetailView } from "@/components/runs/run-detail"
import type { ResultView, RunDetail } from "@/lib/api/types"
import messages from "@/messages/vi.json"

afterEach(cleanup)

function result(over: Partial<ResultView>): ResultView {
  return {
    id: "RUN-0001-TC-000001",
    run_id: "RUN-0001",
    test_case_id: "TC-000001",
    test_case_title: "Đăng nhập",
    status: "PASS",
    reason: "",
    failed_step: null,
    screenshot: null,
    created_at: "2026-11-14T09:00:00Z",
    ...over,
  }
}

function makeRun(over: Partial<RunDetail>): RunDetail {
  return {
    id: "RUN-0001",
    triggered_by: "lead@x.com",
    triggered_by_name: "Lead",
    scope: { screen_ids: [], priorities: [], severities: [] },
    branch: "main",
    commit_sha: "",
    status: "RUNNING",
    started_at: "2026-11-14T09:00:00Z",
    finished_at: null,
    total: 50,
    passed: 1,
    failed: 1,
    tokens_used: 0,
    note: "",
    results: [],
    ...over,
  }
}

function renderDetail(run: RunDetail, props: { canCancel?: boolean; onCancel?: () => void } = {}) {
  render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <RunDetailView
        projectId="PRJ-0001"
        run={run}
        canCancel={props.canCancel ?? false}
        cancelling={false}
        onCancel={props.onCancel ?? vi.fn()}
      />
    </NextIntlClientProvider>,
  )
}

const results = [
  result({}),
  result({
    id: "RUN-0001-TC-000002",
    test_case_id: "TC-000002",
    test_case_title: "Đăng ký",
    status: "FAIL",
    reason: 'Không thấy chữ "Đã gửi" trên trang',
    failed_step: 3,
    screenshot: "RUN-0001/TC-000002.png",
  }),
  result({
    id: "RUN-0001-TC-000003",
    test_case_id: "TC-000003",
    test_case_title: "Quên mật khẩu",
    status: "BLOCKED",
    reason: "Chưa có bước tự động",
  }),
]

describe("RunDetailView", () => {
  it("hiện tiến độ và thống kê từng trạng thái", () => {
    renderDetail(makeRun({ results }))

    expect(screen.getByText("3/50")).toBeInTheDocument()
    expect(screen.getByLabelText("PASS: 1")).toBeInTheDocument()
    expect(screen.getByLabelText("FAIL: 1")).toBeInTheDocument()
    expect(screen.getByLabelText("BLOCKED: 1")).toBeInTheDocument()
    expect(screen.getByLabelText("INCONCLUSIVE: 0")).toBeInTheDocument()
  })

  it("lọc theo trạng thái", () => {
    renderDetail(makeRun({ results }))

    fireEvent.click(screen.getByRole("button", { name: "Lọc FAIL" }))

    expect(screen.getByText("Đăng ký")).toBeInTheDocument()
    expect(screen.queryByText("Đăng nhập")).not.toBeInTheDocument()
    expect(screen.queryByText("Quên mật khẩu")).not.toBeInTheDocument()
  })

  it("case FAIL hiện lý do, số bước và ảnh chụp", () => {
    renderDetail(makeRun({ results }))

    expect(screen.getByText('Không thấy chữ "Đã gửi" trên trang')).toBeInTheDocument()
    expect(screen.getByText("Bước 3")).toBeInTheDocument()
    const image = screen.getByAltText("Ảnh chụp lỗi của TC-000002")
    expect(image).toHaveAttribute(
      "src",
      "/api/projects/PRJ-0001/runs/RUN-0001/screenshots/TC-000002.png",
    )
  })

  it("run FAILED hiện lý do từ note", () => {
    renderDetail(makeRun({ status: "FAILED", note: "App chưa sẵn sàng tại http://localhost:3000" }))

    expect(screen.getByText("App chưa sẵn sàng tại http://localhost:3000")).toBeInTheDocument()
  })

  it("nút Huỷ chỉ hiện khi có quyền và run chưa xong", () => {
    const onCancel = vi.fn()
    renderDetail(makeRun({}), { canCancel: true, onCancel })
    fireEvent.click(screen.getByRole("button", { name: "Huỷ lần chạy" }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    cleanup()

    renderDetail(makeRun({}), { canCancel: false })
    expect(screen.queryByRole("button", { name: "Huỷ lần chạy" })).not.toBeInTheDocument()
    cleanup()

    renderDetail(makeRun({ status: "COMPLETED" }), { canCancel: true })
    expect(screen.queryByRole("button", { name: "Huỷ lần chạy" })).not.toBeInTheDocument()
  })
})

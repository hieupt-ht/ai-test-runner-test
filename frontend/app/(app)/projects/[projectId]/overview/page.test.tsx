import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import ProjectOverviewPage from "@/app/(app)/projects/[projectId]/overview/page"
import type { ProjectStats } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ stats: undefined as ProjectStats | undefined }))

vi.mock("@/lib/use-project-id", () => ({ useProjectId: () => "p1" }))
vi.mock("@/lib/use-stats", () => ({
  useProjectStats: () => ({ data: mocks.stats, isLoading: false }),
}))
// Đồ thị thật nặng và cần đo khung: thay bằng bản in ra props cho dễ kiểm tra
vi.mock("@/components/charts/lazy", () => ({
  LazyPassFailChart: ({ days }: { days: unknown[] }) => <div>chart-passfail-{days.length}</div>,
  LazyCaseStatusDonut: () => <div>chart-donut</div>,
}))

function makeStats(overrides: Partial<ProjectStats> = {}): ProjectStats {
  return {
    total_cases: 128,
    pass_rate: 0.82,
    open_bugs: 14,
    daily: [{ day: "2026-11-19", passed: 1, failed: 0, other: 0 }],
    case_status: { DRAFT: 1, IN_REVIEW: 2, APPROVED: 3, TESTED: 4 },
    screens: [{ screen_id: "SC-1", screen_name: "Đăng nhập", done: 3, total: 4 }],
    ...overrides,
  }
}

function renderPage() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <ProjectOverviewPage />
    </NextIntlClientProvider>,
  )
}

beforeEach(() => {
  mocks.stats = makeStats()
})
afterEach(cleanup)

describe("Tổng quan project", () => {
  it("hiện 3 thẻ số: tổng case, % Pass, bug đang mở", () => {
    renderPage()
    expect(screen.getByText("128")).toBeInTheDocument()
    expect(screen.getByText("82%")).toBeInTheDocument()
    expect(screen.getByText("14")).toBeInTheDocument()
  })

  it("pass_rate null thì hiện dấu gạch", () => {
    mocks.stats = makeStats({ pass_rate: null })
    renderPage()
    expect(screen.getByText("—")).toBeInTheDocument()
  })

  it("có đồ thị Pass/Fail, vòng trạng thái và tiến độ màn hình", () => {
    renderPage()
    expect(screen.getByText("chart-passfail-1")).toBeInTheDocument()
    expect(screen.getByText("chart-donut")).toBeInTheDocument()
    expect(screen.getByText("Đăng nhập")).toBeInTheDocument()
    expect(screen.getByRole("progressbar", { name: "Đăng nhập" })).toHaveAttribute(
      "aria-valuenow",
      "75",
    )
  })

  it("project trống thì không vỡ trang", () => {
    mocks.stats = makeStats({
      total_cases: 0,
      pass_rate: null,
      open_bugs: 0,
      daily: [],
      screens: [],
    })
    renderPage()
    expect(screen.getByText("Chưa có dữ liệu")).toBeInTheDocument()
  })
})

import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, beforeAll, describe, expect, it } from "vitest"

import CaseStatusDonut from "@/components/charts/case-status-donut"
import PassFailChart from "@/components/charts/pass-fail-chart"
import { ProgressList } from "@/components/charts/progress-list"
import type { DayCount } from "@/lib/api/types"
import messages from "@/messages/vi.json"

// jsdom không có ResizeObserver; Recharts cần nó để đo khung. Khung đo ra 0 nên chỉ phần chữ tóm tắt được kiểm tra.
beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})
afterEach(cleanup)

function renderWithIntl(ui: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      {ui}
    </NextIntlClientProvider>,
  )
}

function day(date: string, passed: number, failed: number, other: number): DayCount {
  return { day: date, passed, failed, other }
}

describe("PassFailChart", () => {
  it("tóm tắt tổng Pass/Fail/Khác", () => {
    renderWithIntl(
      <PassFailChart days={[day("2026-11-18", 5, 1, 0), day("2026-11-19", 7, 2, 1)]} />,
    )
    expect(screen.getByText("2 ngày: 12 Pass, 3 Fail, 1 Khác")).toBeInTheDocument()
  })

  it("toàn số 0 thì hiện Chưa có dữ liệu", () => {
    renderWithIntl(<PassFailChart days={[day("2026-11-19", 0, 0, 0)]} />)
    expect(screen.getByText("Chưa có dữ liệu")).toBeInTheDocument()
  })
})

describe("CaseStatusDonut", () => {
  it("tóm tắt từng trạng thái", () => {
    renderWithIntl(
      <CaseStatusDonut counts={{ DRAFT: 4, IN_REVIEW: 3, APPROVED: 2, TESTED: 1 }} />,
    )
    expect(
      screen.getByText("Nháp: 4, Chờ duyệt: 3, Đã duyệt: 2, Đã test: 1"),
    ).toBeInTheDocument()
  })

  it("không có case nào thì hiện Chưa có dữ liệu", () => {
    renderWithIntl(<CaseStatusDonut counts={{ DRAFT: 0, IN_REVIEW: 0, APPROVED: 0, TESTED: 0 }} />)
    expect(screen.getByText("Chưa có dữ liệu")).toBeInTheDocument()
  })
})

describe("ProgressList", () => {
  it("hiện done/total và phần trăm", () => {
    renderWithIntl(<ProgressList items={[{ id: "a", label: "Đăng nhập", done: 3, total: 4 }]} />)
    expect(screen.getByText("Đăng nhập")).toBeInTheDocument()
    expect(screen.getByText("3/4 · 75%")).toBeInTheDocument()
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "75")
  })

  it("total 0 thì không chia cho 0", () => {
    renderWithIntl(<ProgressList items={[{ id: "a", label: "Trống", done: 0, total: 0 }]} />)
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0")
  })

  it("danh sách rỗng thì hiện Chưa có dữ liệu", () => {
    renderWithIntl(<ProgressList items={[]} />)
    expect(screen.getByText("Chưa có dữ liệu")).toBeInTheDocument()
  })
})

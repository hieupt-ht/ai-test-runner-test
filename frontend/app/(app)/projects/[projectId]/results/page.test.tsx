import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import ResultsPage from "@/app/(app)/projects/[projectId]/results/page"
import type { ResultItem } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ useResults: vi.fn() }))

vi.mock("@/lib/use-project-id", () => ({ useProjectId: () => "p1" }))
vi.mock("@/lib/use-results", () => ({ useResults: mocks.useResults }))

const results: ResultItem[] = [
  {
    case_id: "TC-1",
    case_title: "Đăng nhập thành công",
    status: "FAIL",
    reason: "Sai mật khẩu vẫn đăng nhập được",
    failed_step: 2,
    evidence: "javascript:alert(1)",
    run_id: "run-1",
    finished_at: "2026-11-14T10:00:00Z",
  },
  {
    case_id: "TC-2",
    case_title: "Trang chủ tải được",
    status: "PASS",
    reason: "Đúng kết quả mong đợi",
    failed_step: null,
    evidence: "https://example.com/evidence.png",
    run_id: "run-2",
    finished_at: "2026-11-14T11:00:00Z",
  },
]

function renderPage() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <ResultsPage />
    </NextIntlClientProvider>,
  )
}

describe("ResultsPage", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("hiện trạng thái, lý do, bước lỗi và chỉ tạo link an toàn", () => {
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
    const { container } = renderPage()

    expect(screen.getByText("FAIL", { selector: '[data-slot="badge"]' })).toBeInTheDocument()
    expect(screen.getByText("Sai mật khẩu vẫn đăng nhập được")).toBeInTheDocument()
    expect(screen.getByText("Bước lỗi: 2")).toBeInTheDocument()
    expect(container.querySelector('a[href^="javascript:"]')).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute(
      "href",
      "https://example.com/evidence.png",
    )
  })

  it("gọi lại hook khi lọc trạng thái", () => {
    mocks.useResults.mockReturnValue({ data: [], isLoading: false, isError: false })
    renderPage()

    fireEvent.change(screen.getByRole("combobox", { name: "Lọc trạng thái" }), {
      target: { value: "PASS" },
    })
    expect(mocks.useResults).toHaveBeenLastCalledWith("p1", "PASS")
  })

  it("hiện trạng thái rỗng khi chưa có kết quả", () => {
    mocks.useResults.mockReturnValue({ data: [], isLoading: false, isError: false })
    renderPage()

    expect(screen.getByText("Chưa có kết quả test")).toBeInTheDocument()
  })
})

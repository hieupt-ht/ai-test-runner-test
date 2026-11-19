import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import TestCaseDetailPage from "@/app/(app)/projects/[projectId]/test-cases/[caseId]/page"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  testCase: null as unknown,
  project: { archived: false, storage: "cloudinary", require_review: true } as Record<string, unknown>,
}))

vi.mock("@/lib/use-project-id", () => ({ useProjectId: () => "p1" }))
vi.mock("next/navigation", () => ({ useParams: () => ({ caseId: "TC-000001" }) }))
vi.mock("@/lib/use-projects", () => ({ useProject: () => ({ data: mocks.project }) }))
vi.mock("@/lib/use-project-data", () => ({
  useScreens: () => ({ data: [{ id: "SC-0001", name: "Đăng nhập", dev_owner: "nguyenvana" }] }),
}))
vi.mock("@/lib/use-test-cases", () => ({
  useTestCase: () => ({ data: mocks.testCase, isLoading: false }),
  useCaseHistory: () => ({ data: [] }),
}))
// Các khối con đã có test riêng: ở đây chỉ kiểm trang ghép đúng khối nào, ở điều kiện nào.
vi.mock("@/components/test-cases/manual-run-panel", () => ({
  ManualRunPanel: ({ defaultAssignee }: { defaultAssignee?: string }) => (
    <div>khung-chạy-test-tay:{defaultAssignee}</div>
  ),
}))
vi.mock("@/components/test-cases/case-form", () => ({
  CaseForm: ({ onDirtyChange }: { onDirtyChange?: (dirty: boolean) => void }) => (
    <button type="button" onClick={() => onDirtyChange?.(true)}>
      form-sửa-case
    </button>
  ),
}))
vi.mock("@/components/test-cases/review-actions", () => ({
  ReviewActions: () => <div>nút-duyệt</div>,
}))
vi.mock("@/components/test-cases/archive-action", () => ({ ArchiveAction: () => null }))
vi.mock("@/components/test-cases/history-panel", () => ({
  HistoryPanel: () => null,
  commentOf: () => "",
}))
vi.mock("@/components/test-cases/case-read-only", () => ({
  CaseReadOnly: () => <div>case-chỉ-xem</div>,
}))

function makeCase(overrides: Record<string, unknown> = {}) {
  return {
    id: "TC-000001",
    screen_id: "SC-0001",
    title: "Đăng nhập đúng",
    status: "DRAFT",
    version: 2,
    execution_mode: "MANUAL",
    can_edit: true,
    can_run: true,
    can_review: false,
    steps: [{ action: "Mở", expected: "", guide_media: [] }],
    last_result: null,
    ...overrides,
  }
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <TestCaseDetailPage />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
}

describe("Trang chi tiết case – chạy test tay", () => {
  afterEach(() => {
    cleanup()
    mocks.project = { archived: false, storage: "cloudinary", require_review: true }
  })

  it("case Manual có quyền sửa: có khung Chạy test tay, người được giao mặc định là dev màn hình", () => {
    mocks.testCase = makeCase()
    renderPage()
    expect(screen.getByText("khung-chạy-test-tay:nguyenvana")).toBeInTheDocument()
  })

  it("case Automation không có khung Chạy test tay", () => {
    mocks.testCase = makeCase({ execution_mode: "AUTOMATION" })
    renderPage()
    expect(screen.queryByText(/khung-chạy-test-tay/)).not.toBeInTheDocument()
    expect(screen.getByText("nút-duyệt")).toBeInTheDocument()
  })

  it("không có quyền chạy thì không có khung", () => {
    mocks.testCase = makeCase({ can_edit: false, can_run: false })
    renderPage()
    expect(screen.queryByText(/khung-chạy-test-tay/)).not.toBeInTheDocument()
    expect(screen.getByText("Bạn chỉ có quyền xem case này.")).toBeInTheDocument()
  })

  it("người chỉ chạy được thấy khung chạy và dòng nhắc", () => {
    mocks.testCase = makeCase({ can_edit: false, can_run: true })
    renderPage()
    expect(screen.getByText(/khung-chạy-test-tay/)).toBeInTheDocument()
    expect(
      screen.getByText("Case do người khác viết, cần sửa hãy báo người viết hoặc QA Lead"),
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "form-sửa-case" })).not.toBeInTheDocument()
  })

  it("dự án đã lưu trữ thì không có khung", () => {
    mocks.project = { archived: true, storage: "cloudinary", require_review: true }
    mocks.testCase = makeCase()
    renderPage()
    expect(screen.queryByText(/khung-chạy-test-tay/)).not.toBeInTheDocument()
  })

  it.each(["IN_REVIEW", "APPROVED", "DEPRECATED", "ARCHIVED"])(
    "case %s thì không có khung",
    (status) => {
      mocks.testCase = makeCase({ status })
      renderPage()
      expect(screen.queryByText(/khung-chạy-test-tay/)).not.toBeInTheDocument()
    },
  )

  it("form đang sửa dở thì ẩn khung và nhắc lưu trước khi chạy", () => {
    mocks.testCase = makeCase()
    renderPage()
    fireEvent.click(screen.getByRole("button", { name: "form-sửa-case" }))
    expect(screen.queryByText(/khung-chạy-test-tay/)).not.toBeInTheDocument()
    expect(screen.getByText("Hãy lưu thay đổi trước khi chạy test.")).toBeInTheDocument()
  })

  it("case Đã kiểm thử có kết quả gần nhất: nhãn kèm Fail và link sang trang Kết quả", () => {
    mocks.testCase = makeCase({
      status: "TESTED",
      last_result: { status: "FAIL", run_id: "RUN-0001", created_at: "2026-11-18T07:05:00Z" },
    })
    renderPage()
    expect(screen.getByText("Đã kiểm thử · Fail")).toBeInTheDocument()
    expect(screen.getByText(/Lần chạy gần nhất: Fail · RUN-0001 · 18\/11\/2026 14:05/)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Xem trang Kết quả" })).toHaveAttribute(
      "href",
      "/projects/p1/results",
    )
  })

  it("case Nháp không hiện Pass/Fail dù còn kết quả cũ", () => {
    mocks.testCase = makeCase({
      status: "DRAFT",
      last_result: { status: "FAIL", run_id: "RUN-0001", created_at: "2026-11-18T07:05:00Z" },
    })
    renderPage()
    expect(screen.queryByText(/Fail/)).not.toBeInTheDocument()
  })
})

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, within } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import TestCasesPage from "@/app/(app)/projects/[projectId]/test-cases/page"
import type { TestCase } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  cases: [] as unknown[],
  results: [] as unknown[],
  project: { archived: false, permissions: ["EDIT_TEST_CASE"] } as unknown,
  me: { email: "lead@x.vn", role: "QA_LEAD" } as unknown,
  assignments: [] as unknown[],
}))

vi.mock("@/lib/use-project-id", () => ({ useProjectId: () => "p1" }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))
vi.mock("@/lib/use-projects", () => ({
  useProject: () => ({ data: mocks.project }),
}))
vi.mock("@/lib/use-project-data", () => ({
  useScreens: () => ({ data: [{ id: "SC-0001", name: "Đăng nhập" }] }),
  useAssignments: () => ({ data: mocks.assignments }),
}))
vi.mock("@/lib/use-me", () => ({ useMe: () => ({ user: mocks.me, isLoading: false }) }))
vi.mock("@/lib/use-case-import", () => ({
  templateUrl: () => "/template",
  usePreviewImport: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useImportCases: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock("@/lib/use-test-cases", () => ({
  useTestCases: () => ({ data: mocks.cases, isLoading: false, isError: false }),
  useSyncIssues: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock("@/lib/use-results", () => ({
  useResults: () => ({ data: mocks.results }),
}))

function makeCase(overrides: Partial<TestCase>): TestCase {
  return {
    id: "TC-000001",
    screen_id: "SC-0001",
    title: "Đăng nhập đúng",
    severity: "MEDIUM",
    priority: "P2",
    status: "DRAFT",
    created_by: "a@x.vn",
    updated_at: "2026-11-18T00:00:00Z",
    execution_mode: "MANUAL",
    ...overrides,
  } as TestCase
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <TestCasesPage />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
}

function rowOf(id: string) {
  return screen.getByRole("link", { name: id }).closest("tr") as HTMLElement
}

describe("Danh sách test case – cách chạy và kết quả gần nhất", () => {
  afterEach(() => {
    cleanup()
    mocks.cases = []
    mocks.results = []
    mocks.project = { archived: false, permissions: ["EDIT_TEST_CASE"] }
    mocks.me = { email: "lead@x.vn", role: "QA_LEAD" }
    mocks.assignments = []
  })

  it("cột Cách chạy ghi Test tay hoặc Tự động", () => {
    mocks.cases = [
      makeCase({ id: "TC-000001", execution_mode: "MANUAL" }),
      makeCase({ id: "TC-000002", execution_mode: "AUTOMATION" }),
    ]
    renderPage()
    expect(within(rowOf("TC-000001")).getByText("Test tay")).toBeInTheDocument()
    expect(within(rowOf("TC-000002")).getByText("Tự động")).toBeInTheDocument()
  })

  it("có ô lọc theo cách chạy", () => {
    renderPage()
    expect(screen.getByRole("combobox", { name: "Mọi cách chạy" })).toBeInTheDocument()
  })

  it("case Đã kiểm thử hiện thêm Pass/Fail của lần chạy gần nhất", () => {
    mocks.cases = [
      makeCase({ id: "TC-000001", status: "TESTED" }),
      makeCase({ id: "TC-000002", status: "TESTED" }),
    ]
    mocks.results = [
      { case_id: "TC-000001", status: "FAIL" },
      { case_id: "TC-000002", status: "PASS" },
    ]
    renderPage()
    expect(within(rowOf("TC-000001")).getByText("Đã kiểm thử · Fail")).toBeInTheDocument()
    expect(within(rowOf("TC-000002")).getByText("Đã kiểm thử · Pass")).toBeInTheDocument()
  })

  it("case Nháp không hiện Pass/Fail dù còn kết quả cũ", () => {
    mocks.cases = [makeCase({ id: "TC-000001", status: "DRAFT" })]
    mocks.results = [{ case_id: "TC-000001", status: "FAIL" }]
    renderPage()
    expect(within(rowOf("TC-000001")).queryByText(/Fail/)).not.toBeInTheDocument()
  })

  it("QA Lead thấy nút Nhập từ Excel", () => {
    renderPage()
    expect(screen.getByRole("button", { name: "Nhập từ Excel" })).toBeInTheDocument()
  })

  it("tester chưa được giao màn hình nào vẫn thấy nút Nhập từ Excel", () => {
    mocks.me = { email: "t@x.vn", role: "TESTER" }
    renderPage()
    expect(screen.getByRole("button", { name: "Nhập từ Excel" })).toBeInTheDocument()
  })

  it("dự án đã lưu trữ thì không thấy nút Nhập từ Excel", () => {
    mocks.project = { archived: true, permissions: ["EDIT_TEST_CASE"] }
    renderPage()
    expect(screen.queryByRole("button", { name: "Nhập từ Excel" })).not.toBeInTheDocument()
  })
})

import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import OverviewPage from "@/app/(app)/page"
import type { MyAssignment, Project, ResultItem, Role, User } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  role: "TESTER" as Role,
  assignments: [] as MyAssignment[],
  projects: [] as Project[],
  overview: { pending_review: 0, latest_result: null as ResultItem | null },
}))

vi.mock("@/lib/use-me", () => ({
  useMe: () => ({
    user: {
      email: "user@example.com",
      name: "Nguyễn An",
      role: mocks.role,
      active: true,
      created_at: "2026-11-01T00:00:00Z",
    } satisfies User,
    isLoading: false,
  }),
}))
vi.mock("@/lib/use-project-data", () => ({
  useMyAssignments: () => ({ data: mocks.assignments, isLoading: false }),
}))
vi.mock("@/lib/use-projects", () => ({
  useProjects: () => ({ data: mocks.projects, isLoading: false }),
}))
vi.mock("@/lib/use-overview", () => ({
  useOverview: () => ({ data: mocks.overview, isLoading: false }),
}))

const activeAssignment: MyAssignment = {
  assignment_id: "a1",
  project_id: "p1",
  project_name: "Dự án A",
  screen_id: "SCR-1",
  screen_name: "Đăng nhập",
  deadline: "2026-11-16",
  status: "WRITING",
  case_counts: { IN_REVIEW: 2 },
  returned_cases: [
    { case_id: "TC-1", title: "Đăng nhập sai", comment: "Thiếu bước", returned_by: "qa@example.com" },
  ],
}

const project: Project = {
  id: "p1",
  name: "Dự án A",
  repo_full_name: "org/repo",
  branch: "main",
  staging_url: "https://staging.example.com",
  spreadsheet_id: "sheet-1",
  archived: false,
  created_at: "2026-11-01T00:00:00Z",
}

const result: ResultItem = {
  case_id: "TC-1",
  case_title: "Đăng nhập thành công",
  screen_id: "SC-login",
  screen_name: "Đăng nhập",
  status: "PASS",
  reason: "Đúng kết quả mong đợi",
  failed_step: null,
  evidence: "",
  run_id: "run-1",
  finished_at: "2026-11-14T10:00:00Z",
}

function renderPage() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <OverviewPage />
    </NextIntlClientProvider>,
  )
}

describe("OverviewPage", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-11-14T00:00:00+07:00"))
    mocks.assignments = []
    mocks.projects = []
    mocks.overview = { pending_review: 0, latest_result: null }
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it("Tester chỉ thấy việc đang làm, việc sắp hết hạn và case bị trả lại", () => {
    mocks.role = "TESTER"
    mocks.assignments = [activeAssignment]
    renderPage()

    expect(screen.getByText("Việc đang làm")).toBeInTheDocument()
    expect(screen.getByText("Sắp hết hạn")).toBeInTheDocument()
    expect(screen.getByText("Case bị trả lại")).toBeInTheDocument()
    expect(screen.getAllByText("1")).toHaveLength(3)
    expect(screen.queryByText("Chờ duyệt")).not.toBeInTheDocument()
    expect(screen.queryByText("Tổng số dự án")).not.toBeInTheDocument()
  })

  it("QA Lead chỉ thấy việc chờ duyệt và kết quả gần nhất", () => {
    mocks.role = "QA_LEAD"
    mocks.assignments = []
    mocks.projects = [project]
    mocks.overview = { pending_review: 2, latest_result: result }
    renderPage()

    expect(screen.getByText("Chờ duyệt")).toBeInTheDocument()
    expect(screen.getByText("2")).toBeInTheDocument()
    expect(screen.getByText("Kết quả gần nhất")).toBeInTheDocument()
    expect(screen.getByText("PASS")).toBeInTheDocument()
    expect(screen.queryByText("Việc đang làm")).not.toBeInTheDocument()
    expect(screen.queryByText("Tổng số dự án")).not.toBeInTheDocument()
  })

  it("Admin chỉ thấy tổng số dự án và kết quả gần nhất", () => {
    mocks.role = "ADMIN"
    mocks.projects = [project]
    mocks.overview = { pending_review: 0, latest_result: result }
    renderPage()

    expect(screen.getByText("Tổng số dự án")).toBeInTheDocument()
    expect(screen.getByText("1")).toBeInTheDocument()
    expect(screen.getByText("Kết quả gần nhất")).toBeInTheDocument()
    expect(screen.queryByText("Việc đang làm")).not.toBeInTheDocument()
    expect(screen.queryByText("Chờ duyệt")).not.toBeInTheDocument()
  })

  it("hiện chữ giải thích khi vai trò chưa có dữ liệu", () => {
    mocks.role = "ADMIN"
    renderPage()

    expect(screen.getByText("Chưa có dự án nào.")).toBeInTheDocument()
    expect(screen.getByText("Chưa có kết quả test.")).toBeInTheDocument()
  })
})

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import ScreenDetailPage from "@/app/(app)/projects/[projectId]/screens/[screenId]/page"
import type { Assignment, Screen, TestCase, User } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  screenId: "SC-0001",
  user: null as unknown,
  permissions: [] as string[],
  screens: [] as unknown[],
  assignments: [] as unknown[],
  cases: [] as unknown[],
}))

vi.mock("@/lib/use-project-id", () => ({ useProjectId: () => "p1" }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  useParams: () => ({ screenId: mocks.screenId }),
}))
vi.mock("@/lib/use-me", () => ({ useMe: () => ({ user: mocks.user, isLoading: false }) }))
vi.mock("@/lib/use-projects", () => ({
  useProject: () => ({
    data: { storage: "cloudinary", archived: false, permissions: mocks.permissions },
  }),
}))
vi.mock("@/lib/use-project-data", () => ({
  useScreens: () => ({ data: mocks.screens, isLoading: false }),
  useAssignments: () => ({ data: mocks.assignments }),
  useSaveScreen: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock("@/lib/use-test-cases", () => ({
  useTestCases: () => ({ data: mocks.cases, isLoading: false }),
}))

const sc1 = {
  id: "SC-0001",
  name: "Đăng nhập",
  description: "Màn hình đăng nhập",
  route: "/login",
  code_paths: [],
  created_at: "2026-11-17T00:00:00Z",
  dev_owner: "nguyenvana",
  media: [],
} satisfies Screen
const sc2 = { ...sc1, id: "SC-0002", name: "Trang chủ" }

function makeCase(id: string, screenId: string, title: string) {
  return {
    id,
    screen_id: screenId,
    title,
    status: "APPROVED",
    severity: "HIGH",
    platform: "WEB",
  } as unknown as TestCase
}

const tester = { email: "t@x.vn", role: "TESTER" } as unknown as User
const lead = { email: "lead@x.vn", role: "QA_LEAD" } as unknown as User

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ScreenDetailPage />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
}

describe("ScreenDetailPage", () => {
  beforeEach(() => {
    mocks.screenId = "SC-0001"
    mocks.user = tester
    mocks.permissions = ["EDIT_TEST_CASE"]
    mocks.screens = [sc1, sc2]
    mocks.assignments = []
    mocks.cases = [
      makeCase("TC-000001", "SC-0001", "Đăng nhập đúng"),
      makeCase("TC-000002", "SC-0002", "Mở trang chủ"),
    ]
  })
  afterEach(() => {
    cleanup()
    mocks.push.mockReset()
  })

  it("hiện thông tin màn hình và chỉ case của màn hình đó", () => {
    renderPage()
    expect(screen.getByText("Đăng nhập")).toBeInTheDocument()
    expect(screen.getByText("/login")).toBeInTheDocument()
    expect(screen.getByText("TC-000001")).toBeInTheDocument()
    expect(screen.queryByText("TC-000002")).not.toBeInTheDocument()
  })

  it("không tìm thấy màn hình", () => {
    mocks.screenId = "SC-9999"
    renderPage()
    expect(screen.getByText("Không tìm thấy màn hình")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Màn hình/ })).toHaveAttribute(
      "href",
      "/projects/p1/screens",
    )
  })

  it("tester chưa được giao không thấy nút Tạo case và Sửa", () => {
    renderPage()
    expect(screen.queryByRole("link", { name: "Tạo case" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Sửa" })).not.toBeInTheDocument()
  })

  it("QA Lead thấy cả hai", () => {
    mocks.user = lead
    mocks.permissions = ["EDIT_TEST_CASE", "MANAGE_SCREENS"]
    renderPage()
    expect(screen.getByRole("link", { name: "Tạo case" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Sửa" })).toBeInTheDocument()
  })

  it("tester được giao thấy Tạo case với link ?screen=SC-0001", () => {
    mocks.assignments = [
      { screen_id: "SC-0001", assignee_email: "t@x.vn" } as unknown as Assignment,
    ]
    renderPage()
    expect(screen.getByRole("link", { name: "Tạo case" })).toHaveAttribute(
      "href",
      "/projects/p1/test-cases/new?screen=SC-0001",
    )
  })

  it("bấm dòng case thì mở case đó", () => {
    renderPage()
    fireEvent.click(screen.getByText("Đăng nhập đúng"))
    expect(mocks.push).toHaveBeenCalledWith("/projects/p1/test-cases/TC-000001")
  })
})

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ModuleSection } from "@/components/modules/module-section"
import type { Assignment, MemberView, ModuleView, Screen } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const unassign = vi.fn()
let assignments: Assignment[] = []

vi.mock("@/lib/use-modules", () => ({
  useAssignModule: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUnassignModule: () => ({ mutateAsync: unassign, isPending: false }),
  useDeleteModule: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSaveModule: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock("@/lib/use-project-data", () => ({
  useAssignments: () => ({ data: assignments }),
}))

const module_: ModuleView = {
  id: "MD-0001",
  name: "Tài khoản",
  description: "",
  created_at: "2026-11-26T00:00:00Z",
  screen_count: 2,
  workers: [{ assignment_id: "MA-0001", email: "an@x.com", name: "An", deadline: "2099-12-20" }],
}
const screens = [
  { id: "SC-0001", name: "Đăng ký", module_id: "MD-0001" },
  { id: "SC-0002", name: "Hồ sơ", module_id: "MD-0001" },
] as Screen[]
const testers = [{ email: "an@x.com", name: "An", role: "TESTER", active: true }] as MemberView[]

function show(props: { canManage: boolean; meEmail: string; canClaim: boolean }) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ModuleSection
          projectId="P1"
          module={module_}
          screens={screens}
          testers={testers}
          defaultOpen
          {...props}
        >
          <p>bảng màn hình</p>
        </ModuleSection>
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  unassign.mockReset()
  assignments = []
})

describe("ModuleSection", () => {
  it("shows name, screen count, workers with deadline and children", () => {
    show({ canManage: false, meEmail: "binh@x.com", canClaim: true })

    expect(screen.getByText("Tài khoản")).toBeInTheDocument()
    expect(screen.getByText("2 màn hình")).toBeInTheDocument()
    expect(screen.getByText("Đang làm: An (20/12)")).toBeInTheDocument()
    expect(screen.getByText("bảng màn hình")).toBeInTheDocument()
  })

  it("qa sees Giao, tester sees Nhận", () => {
    show({ canManage: true, meEmail: "lead@x.com", canClaim: false })
    expect(screen.getByRole("button", { name: /^Giao/ })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /^Nhận/ })).not.toBeInTheDocument()
    cleanup()

    show({ canManage: false, meEmail: "binh@x.com", canClaim: true })
    expect(screen.getByRole("button", { name: /^Nhận/ })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /^Giao/ })).not.toBeInTheDocument()
  })

  it("tester already working sees Bỏ nhận with the number of screen assignments", () => {
    assignments = [
      { id: "AS-1", screen_id: "SC-0001", assignee_email: "an@x.com" },
      { id: "AS-2", screen_id: "SC-0002", assignee_email: "an@x.com" },
      { id: "AS-3", screen_id: "SC-0099", assignee_email: "an@x.com" },
    ] as Assignment[]
    show({ canManage: false, meEmail: "an@x.com", canClaim: true })

    expect(screen.queryByRole("button", { name: /^Nhận/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /Bỏ nhận/ }))

    expect(screen.getByText(/Sẽ bỏ 2 việc giao màn hình trong module/)).toBeInTheDocument()
  })
})

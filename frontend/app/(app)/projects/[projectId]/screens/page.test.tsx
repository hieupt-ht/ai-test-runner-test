import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import ScreensPage from "@/app/(app)/projects/[projectId]/screens/page"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  me: { email: "t@x.com", role: "TESTER" } as unknown,
  project: { archived: false, permissions: ["EDIT_TEST_CASE"] } as unknown,
}))

vi.mock("@/lib/use-project-id", () => ({ useProjectId: () => "p1" }))
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }))
vi.mock("@/lib/use-projects", () => ({ useProject: () => ({ data: mocks.project }) }))
vi.mock("@/lib/use-me", () => ({ useMe: () => ({ user: mocks.me, isLoading: false }) }))
vi.mock("@/lib/use-modules", () => ({
  useModules: () => ({ data: [], isLoading: false }),
  useSaveModule: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock("@/lib/use-project-data", () => ({
  useScreens: () => ({ data: [], isLoading: false }),
  useMembers: () => ({ data: [] }),
  useDeleteScreen: () => ({ mutateAsync: vi.fn() }),
}))
vi.mock("@/lib/use-test-cases", () => ({ useTestCases: () => ({ data: [] }) }))
vi.mock("@/components/screens/screen-form-dialog", () => ({
  ScreenFormDialog: ({ triggerLabel }: { triggerLabel: React.ReactNode }) => (
    <button type="button">{triggerLabel}</button>
  ),
}))

function renderPage() {
  render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <ScreensPage />
    </NextIntlClientProvider>,
  )
}

describe("Trang Màn hình", () => {
  afterEach(cleanup)

  it("tester thấy nút Thêm module nhưng không thấy nút Thêm màn hình", () => {
    renderPage()
    expect(screen.getByRole("button", { name: /Thêm module/ })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Thêm màn hình/ })).not.toBeInTheDocument()
  })

  it("QA Lead thấy cả hai nút", () => {
    mocks.me = { email: "l@x.com", role: "QA_LEAD" }
    mocks.project = { archived: false, permissions: ["EDIT_TEST_CASE", "MANAGE_SCREENS"] }
    renderPage()
    expect(screen.getByRole("button", { name: /Thêm module/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Thêm màn hình/ })).toBeInTheDocument()
  })
})

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ModuleWorkDialog } from "@/components/modules/module-work-dialog"
import type { MemberView, ModuleView } from "@/lib/api/types"
import { addDays, todayInVietnam } from "@/lib/deadline"
import messages from "@/messages/vi.json"

const mutateAsync = vi.fn()
vi.mock("@/lib/use-modules", () => ({
  useAssignModule: () => ({ mutateAsync, isPending: false }),
}))

const base: ModuleView = {
  id: "MD-0001",
  name: "Tài khoản",
  description: "",
  created_at: "2026-11-26T00:00:00Z",
  screen_count: 3,
  workers: [],
}

const FAR = "2099-12-20"
const NEAR = "2099-12-05"

const testers = [
  { email: "an@x.com", name: "An", role: "TESTER", active: true },
  { email: "binh@x.com", name: "Bình", role: "TESTER", active: true },
] as MemberView[]

function open(module: ModuleView, mode: "claim" | "assign" = "claim") {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ModuleWorkDialog
          projectId="P1"
          module={module}
          mode={mode}
          testers={testers}
          meEmail="an@x.com"
          trigger={<button type="button" />}
          triggerLabel="Mở"
        />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByText("Mở"))
}

afterEach(() => {
  cleanup()
  mutateAsync.mockReset()
})

describe("ModuleWorkDialog", () => {
  it("shows red warning but keeps claim enabled when someone else works on module", () => {
    open({
      ...base,
      workers: [{ assignment_id: "MA-0001", email: "binh@x.com", name: "Bình", deadline: FAR }],
    })

    const warning = screen.getByText("Bình đang làm module này. Bạn vẫn có thể nhận để làm cùng.")
    expect(warning).toHaveClass("text-destructive")
    expect(screen.getByRole("button", { name: "Nhận module" })).toBeEnabled()
  })

  it("no warning when nobody works on module", () => {
    open(base)

    expect(screen.queryByText(/đang làm module này/)).not.toBeInTheDocument()
  })

  it("does not warn about myself", () => {
    open({
      ...base,
      workers: [{ assignment_id: "MA-0001", email: "an@x.com", name: "An", deadline: FAR }],
    })

    expect(screen.queryByText(/đang làm module này/)).not.toBeInTheDocument()
  })

  it("default deadline is latest worker deadline", () => {
    open({
      ...base,
      workers: [
        { assignment_id: "MA-0001", email: "binh@x.com", name: "Bình", deadline: NEAR },
        { assignment_id: "MA-0002", email: "c@x.com", name: "Chi", deadline: FAR },
      ],
    })

    expect(screen.getByLabelText("Deadline")).toHaveValue(FAR)
  })

  it("recomputes the default deadline each time the dialog opens", () => {
    const tree = (module: ModuleView) => (
      <QueryClientProvider client={new QueryClient()}>
        <NextIntlClientProvider locale="vi" messages={messages}>
          <ModuleWorkDialog
            projectId="P1"
            module={module}
            mode="claim"
            testers={testers}
            meEmail="an@x.com"
            trigger={<button type="button" />}
            triggerLabel="Mở"
          />
        </NextIntlClientProvider>
      </QueryClientProvider>
    )
    const { rerender } = render(tree(base)) // dữ liệu module về chậm: lúc đầu chưa có ai làm
    rerender(
      tree({
        ...base,
        workers: [{ assignment_id: "MA-0002", email: "c@x.com", name: "Chi", deadline: FAR }],
      }),
    )

    fireEvent.click(screen.getByText("Mở"))

    expect(screen.getByLabelText("Deadline")).toHaveValue(FAR)
  })

  it("default deadline is today + 7 days when nobody works", () => {
    open(base)

    expect(screen.getByLabelText("Deadline")).toHaveValue(addDays(todayInVietnam(), 7))
  })

  it("claim sends only my own email", async () => {
    mutateAsync.mockResolvedValue([])
    open(base)

    fireEvent.click(screen.getByRole("button", { name: "Nhận module" }))

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({
      moduleId: "MD-0001",
      emails: ["an@x.com"],
    })
  })

  it("assign mode sends the chosen testers", async () => {
    mutateAsync.mockResolvedValue([])
    open(base, "assign")

    fireEvent.click(screen.getByLabelText(/Bình/))
    fireEvent.click(screen.getByRole("button", { name: "Giao module" }))

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({ emails: ["binh@x.com"] })
  })
})

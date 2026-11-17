import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it } from "vitest"

import { UserTable } from "@/components/users/user-table"
import type { User } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const USERS: User[] = [
  { email: "admin@x.com", name: "Admin", role: "ADMIN", active: true, created_at: "2026-11-12T00:00:00Z" },
  { email: "an@x.com", name: "An", role: "TESTER", active: true, created_at: "2026-11-12T00:00:00Z" },
]

function renderTable() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <QueryClientProvider client={new QueryClient()}>
        <UserTable users={USERS} currentUserEmail="admin@x.com" />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  )
}

describe("UserTable", () => {
  afterEach(cleanup)

  it("cho đổi vai trò của người khác, nhưng không cho tự đổi vai trò của mình", () => {
    renderTable()

    const selfRole = screen.getByRole("combobox", { name: "Vai trò của admin@x.com" })
    const otherRole = screen.getByRole("combobox", { name: "Vai trò của an@x.com" })

    expect(selfRole).toHaveAttribute("data-disabled")
    expect(otherRole).not.toHaveAttribute("data-disabled")
  })

  it("có nút đặt lại mật khẩu ở mỗi dòng, mở hộp thoại khi bấm", async () => {
    renderTable()

    expect(screen.getAllByRole("button", { name: /Đặt lại mật khẩu của/ })).toHaveLength(2)
    fireEvent.click(screen.getByRole("button", { name: "Đặt lại mật khẩu của an@x.com" }))

    expect(await screen.findByLabelText("Mật khẩu mới")).toBeInTheDocument()
  })
})

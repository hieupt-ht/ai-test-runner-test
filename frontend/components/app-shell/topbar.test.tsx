import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { Topbar } from "@/components/app-shell/topbar"
import messages from "@/messages/vi.json"

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }))
vi.mock("next-themes", () => ({ useTheme: () => ({ setTheme: vi.fn() }) }))
vi.mock("@/components/notifications/notification-bell", () => ({ NotificationBell: () => null }))

describe("Topbar", () => {
  afterEach(cleanup)

  it("menu người dùng mở hộp thoại đổi mật khẩu", async () => {
    render(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <QueryClientProvider client={new QueryClient()}>
          <Topbar
            user={{ email: "an@x.com", name: "An", role: "TESTER", active: true, created_at: "2026-11-12T00:00:00Z" }}
            title="Trang"
          />
        </QueryClientProvider>
      </NextIntlClientProvider>,
    )

    fireEvent.click(screen.getByRole("button", { name: /An/ }))
    fireEvent.click(await screen.findByRole("menuitem", { name: /Đổi mật khẩu/ }))

    expect(await screen.findByLabelText("Mật khẩu hiện tại")).toBeInTheDocument()
  })
})

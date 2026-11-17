import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { UserFormDialog } from "@/components/users/user-form-dialog"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ post: vi.fn() }))

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: { POST: mocks.post, GET: vi.fn() },
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

describe("UserFormDialog", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("gửi kèm mật khẩu khi tạo người dùng", async () => {
    mocks.post.mockResolvedValue({ data: { email: "an@x.com" }, response: { ok: true } })
    render(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <QueryClientProvider client={new QueryClient()}>
          <UserFormDialog />
        </QueryClientProvider>
      </NextIntlClientProvider>,
    )

    fireEvent.click(screen.getByRole("button", { name: /Thêm người dùng/ }))
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "an@x.com" } })
    fireEvent.change(screen.getByLabelText("Tên hiển thị"), { target: { value: "An" } })
    fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: "mat-khau-12" } })
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }))

    await waitFor(() =>
      expect(mocks.post).toHaveBeenCalledWith("/api/users", {
        body: { email: "an@x.com", name: "An", role: "TESTER", password: "mat-khau-12" },
      }),
    )
  })
})

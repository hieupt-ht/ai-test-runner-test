import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ResetPasswordDialog } from "@/components/users/reset-password-dialog"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ post: vi.fn(), success: vi.fn() }))

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: { POST: mocks.post },
}))
vi.mock("sonner", () => ({ toast: { success: mocks.success, error: vi.fn() } }))

function renderDialog(onOpenChange = vi.fn()) {
  render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <QueryClientProvider client={new QueryClient()}>
        <ResetPasswordDialog email="an@x.com" open onOpenChange={onOpenChange} />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  )
  return onOpenChange
}

function submit(password: string) {
  fireEvent.change(screen.getByLabelText("Mật khẩu mới"), { target: { value: password } })
  fireEvent.click(screen.getByRole("button", { name: "Đặt lại" }))
}

describe("ResetPasswordDialog", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("báo lỗi và không gọi API khi mật khẩu ngắn hơn 8 ký tự", async () => {
    renderDialog()

    submit("1234567")

    expect(await screen.findByText("Mật khẩu tối thiểu 8 ký tự")).toBeInTheDocument()
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it("gọi API đặt lại mật khẩu rồi đóng hộp thoại", async () => {
    mocks.post.mockResolvedValue({ response: { ok: true, status: 204 } })
    const onOpenChange = renderDialog()

    submit("mat-khau-moi-12")

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    expect(mocks.post).toHaveBeenCalledWith("/api/users/{email}/reset-password", {
      params: { path: { email: "an@x.com" } },
      body: { password: "mat-khau-moi-12" },
    })
    expect(mocks.success).toHaveBeenCalled()
  })

  it("hiện câu báo lỗi 404 của server", async () => {
    mocks.post.mockResolvedValue({
      error: { detail: "Không tìm thấy người dùng" },
      response: { ok: false, status: 404 },
    })
    renderDialog()

    submit("mat-khau-moi-12")

    expect(await screen.findByRole("alert")).toHaveTextContent("Không tìm thấy người dùng")
  })
})

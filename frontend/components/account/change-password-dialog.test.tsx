import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChangePasswordDialog } from "@/components/account/change-password-dialog"
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
        <ChangePasswordDialog open onOpenChange={onOpenChange} />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  )
  return onOpenChange
}

function fillAndSubmit(current: string, next: string, confirm: string) {
  fireEvent.change(screen.getByLabelText("Mật khẩu hiện tại"), { target: { value: current } })
  fireEvent.change(screen.getByLabelText("Mật khẩu mới"), { target: { value: next } })
  fireEvent.change(screen.getByLabelText("Nhập lại mật khẩu mới"), { target: { value: confirm } })
  fireEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }))
}

describe("ChangePasswordDialog", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("bắt buộc nhập lại khớp với mật khẩu mới", async () => {
    renderDialog()

    fillAndSubmit("cu-12345", "moi-12345", "moi-khac-1")

    expect(await screen.findByText("Hai mật khẩu mới chưa khớp nhau")).toBeInTheDocument()
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it("từ chối mật khẩu mới ngắn hơn 8 ký tự", async () => {
    renderDialog()

    fillAndSubmit("cu-12345", "1234567", "1234567")

    expect(await screen.findByText("Mật khẩu tối thiểu 8 ký tự")).toBeInTheDocument()
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it("hiện câu báo lỗi của server khi sai mật khẩu hiện tại", async () => {
    mocks.post.mockResolvedValue({
      error: { detail: "Mật khẩu hiện tại không đúng" },
      response: { ok: false, status: 400 },
    })
    renderDialog()

    fillAndSubmit("sai-12345", "moi-12345", "moi-12345")

    expect(await screen.findByRole("alert")).toHaveTextContent("Mật khẩu hiện tại không đúng")
  })

  it("đóng hộp thoại và báo thành công khi server trả 204", async () => {
    mocks.post.mockResolvedValue({ response: { ok: true, status: 204 } })
    const onOpenChange = renderDialog()

    fillAndSubmit("cu-12345", "moi-12345", "moi-12345")

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    expect(mocks.post).toHaveBeenCalledWith("/api/auth/change-password", {
      body: { current_password: "cu-12345", new_password: "moi-12345" },
    })
    expect(mocks.success).toHaveBeenCalledWith("Đã đổi mật khẩu")
  })
})

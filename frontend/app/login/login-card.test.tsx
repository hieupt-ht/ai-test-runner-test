import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { LoginCard } from "@/app/login/login-card"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ post: vi.fn(), replace: vi.fn() }))

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  api: { POST: mocks.post },
}))
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: mocks.replace }) }))

function renderCard() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <LoginCard />
    </NextIntlClientProvider>,
  )
}

function fillAndSubmit(email = "an@x.com", password = "mat-khau-12") {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } })
  fireEvent.change(screen.getByLabelText("Mật khẩu"), { target: { value: password } })
  fireEvent.click(screen.getByRole("button", { name: "Đăng nhập" }))
}

describe("LoginCard", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("có ô email và mật khẩu, không còn nút Google", () => {
    renderCard()

    expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email")
    expect(screen.getByLabelText("Mật khẩu")).toHaveAttribute("type", "password")
    expect(screen.queryByText(/google/i)).not.toBeInTheDocument()
  })

  it("gửi email và mật khẩu, đăng nhập được thì về trang chủ", async () => {
    mocks.post.mockResolvedValue({ data: { email: "an@x.com" }, response: { ok: true, status: 200 } })
    renderCard()

    fillAndSubmit()

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/"))
    expect(mocks.post).toHaveBeenCalledWith("/api/auth/login", {
      body: { email: "an@x.com", password: "mat-khau-12" },
    })
  })

  it("hiện đúng câu báo lỗi của server khi sai mật khẩu (401)", async () => {
    mocks.post.mockResolvedValue({
      error: { detail: "Email hoặc mật khẩu không đúng" },
      response: { ok: false, status: 401 },
    })
    renderCard()

    fillAndSubmit()

    expect(await screen.findByRole("alert")).toHaveTextContent("Email hoặc mật khẩu không đúng")
    expect(mocks.replace).not.toHaveBeenCalled()
  })

  it("hiện câu báo khoá của server khi sai quá nhiều lần (429)", async () => {
    mocks.post.mockResolvedValue({
      error: { detail: "Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút" },
      response: { ok: false, status: 429 },
    })
    renderCard()

    fillAndSubmit()

    expect(await screen.findByRole("alert")).toHaveTextContent("sau 15 phút")
  })

  it("làm mờ nút khi đang gửi", async () => {
    mocks.post.mockReturnValue(new Promise(() => {})) // không bao giờ xong
    renderCard()

    fillAndSubmit()

    await waitFor(() => expect(screen.getByRole("button", { name: "Đăng nhập" })).toBeDisabled())
  })
})

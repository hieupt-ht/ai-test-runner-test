import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { CaseForm } from "@/components/test-cases/case-form"
import messages from "@/messages/vi.json"

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock("@/lib/use-test-cases", () => ({
  useCreateTestCase: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateTestCase: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useTransitionTestCase: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRefreshCases: () => vi.fn(),
}))
// Ô chọn ảnh thật cần mạng; ở đây chỉ cần giả lập "đang tải lên".
vi.mock("@/components/media/media-picker", () => ({
  MediaPicker: ({ onBusyChange }: { onBusyChange?: (busy: boolean) => void }) => (
    <button type="button" onClick={() => onBusyChange?.(true)}>
      giả-lập-tải-lên
    </button>
  ),
}))

function renderForm() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <CaseForm
          projectId="PRJ-0001"
          screens={[{ id: "SC-0001", name: "Đăng nhập" } as never]}
          defaultScreenId="SC-0001"
        />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
}

describe("CaseForm", () => {
  afterEach(cleanup)

  it("có ô Nền tảng, Loại, Regression và Bắt đầu tại", () => {
    renderForm()
    expect(screen.getByRole("combobox", { name: "Nền tảng" })).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: "Loại test" })).toBeInTheDocument()
    expect(screen.getByRole("checkbox", { name: "Regression" })).not.toBeChecked()
    expect(screen.getByLabelText("Bắt đầu tại")).toBeInTheDocument()
  })

  it("nhắc không chụp mật khẩu hay thông tin cá nhân", () => {
    renderForm()
    expect(
      screen.getByText(
        "Đừng chụp mật khẩu hoặc thông tin cá nhân; ảnh có thể hiện trong issue công khai.",
      ),
    ).toBeInTheDocument()
  })

  it("gom điều kiện, dữ liệu, điều kiện sau, mã yêu cầu vào một mục thu gọn", () => {
    renderForm()
    const summary = screen.getByText("Điều kiện, dữ liệu, ...")
    const section = summary.closest("details") as HTMLElement
    expect(section).not.toBeNull()
    expect(section).not.toHaveAttribute("open")
    for (const label of [
      "Điều kiện tiên quyết",
      "Dữ liệu kiểm thử",
      "Điều kiện sau",
      "Mã yêu cầu",
    ]) {
      expect(within(section).getByLabelText(label)).toBeInTheDocument()
    }
  })

  it("khoá nút Lưu và Gửi khi còn đang tải ảnh/video", () => {
    renderForm()
    expect(screen.getByRole("button", { name: "Lưu nháp" })).toBeEnabled()

    fireEvent.click(screen.getAllByRole("button", { name: "giả-lập-tải-lên" })[0])

    expect(screen.getByRole("button", { name: "Lưu nháp" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Lưu và gửi duyệt" })).toBeDisabled()
  })
})

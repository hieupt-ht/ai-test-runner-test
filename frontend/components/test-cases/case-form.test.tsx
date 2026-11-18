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
// Dự án này lưu ảnh/video ở Drive: form phải chuyển thông tin đó xuống ô chọn ảnh.
vi.mock("@/lib/use-projects", () => ({
  useProject: () => ({ data: { storage: "drive" } }),
}))
vi.mock("@/components/media/media-picker", () => ({
  MediaPicker: ({
    onBusyChange,
    storage,
  }: {
    onBusyChange?: (busy: boolean) => void
    storage?: string
  }) => (
    <button type="button" data-storage={storage} onClick={() => onBusyChange?.(true)}>
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

  it("truyền nơi lưu của dự án cho ô chọn ảnh/video", () => {
    renderForm()
    const pickers = screen.getAllByRole("button", { name: "giả-lập-tải-lên" })
    expect(pickers.length).toBeGreaterThan(0)
    for (const picker of pickers) expect(picker).toHaveAttribute("data-storage", "drive")
  })

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

describe("CaseForm – màn hình", () => {
  afterEach(cleanup)

  function renderWithScreens(screens: unknown[], defaultScreenId?: string) {
    return render(
      <QueryClientProvider client={new QueryClient()}>
        <NextIntlClientProvider locale="vi" messages={messages}>
          <CaseForm
            projectId="PRJ-0001"
            screens={screens as never}
            defaultScreenId={defaultScreenId}
          />
        </NextIntlClientProvider>
      </QueryClientProvider>,
    )
  }

  it("chọn màn hình có ảnh thì hiện ảnh của màn hình đó", () => {
    const url = "https://res.cloudinary.com/demo/image/upload/login.png"
    renderWithScreens(
      [
        {
          id: "SC-0001",
          name: "Đăng nhập",
          media: [{ kind: "image", public_id: "guide/login", url, note: "" }],
        },
      ],
      "SC-0001",
    )
    expect(screen.getByRole("img")).toHaveAttribute("src", url)
  })

  it("danh sách màn hình trống thì nhắc nhờ QA Lead giao việc", () => {
    renderWithScreens([])
    expect(
      screen.getByText(
        "Bạn chưa được giao màn hình nào để viết test case. Hãy nhờ QA Lead giao việc.",
      ),
    ).toBeInTheDocument()
  })
})

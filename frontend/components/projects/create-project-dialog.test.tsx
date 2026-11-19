import { fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { describe, expect, it, vi } from "vitest"

import { CreateProjectDialog } from "@/components/projects/create-project-dialog"
import messages from "@/messages/vi.json"

vi.mock("@/lib/use-projects", () => ({
  useGithubRepositories: () => ({ data: [], error: null }),
  useGithubBranches: () => ({ data: [] }),
  useServiceAccountEmail: () => ({ data: "service@example.com" }),
  useCreateProject: () => ({ isPending: false, mutateAsync: vi.fn() }),
}))

describe("CreateProjectDialog", () => {
  it("giới hạn chiều cao, cuộn được và vẫn có các trường cùng nút lưu", () => {
    render(
      <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
        <CreateProjectDialog />
      </NextIntlClientProvider>,
    )

    fireEvent.click(screen.getByRole("button", { name: "Tạo dự án" }))

    const dialog = screen.getByRole("dialog")
    expect(dialog).toHaveClass("max-h-[calc(100dvh-2rem)]", "overflow-y-auto")
    expect(screen.getByLabelText("Tên dự án")).toBeInTheDocument()
    expect(screen.getByLabelText("Staging URL (không bắt buộc)")).toBeInTheDocument()
    expect(screen.getByLabelText("Link hoặc ID Google Sheet")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Lưu" })).toBeEnabled()
  })

  it("không bị thanh cuộn ngang: cột duy nhất của hộp thoại được phép co lại", () => {
    render(
      <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
        <CreateProjectDialog />
      </NextIntlClientProvider>,
    )
    fireEvent.click(screen.getByRole("button", { name: "Tạo dự án" }))

    // Hộp thoại là grid; cột "auto" nở theo nội dung dài (email, link) nên phải ép cột co được
    expect(screen.getByRole("dialog")).toHaveClass("grid-cols-[minmax(0,1fr)]", "overflow-x-hidden")
  })
})

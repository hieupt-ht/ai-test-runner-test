import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { toast } from "sonner"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog"
import { ApiError } from "@/lib/api/client"
import type { Project } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ remove: vi.fn() }))

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))
vi.mock("@/lib/use-projects", () => ({
  useDeleteProject: () => ({
    mutateAsync: (name: string) => mocks.remove(name),
    isPending: false,
  }),
}))

const project = { id: "PRJ-0001", name: "Dự án A", archived: true } as Project

function open() {
  render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <DeleteProjectDialog project={project} />
    </NextIntlClientProvider>,
  )
  fireEvent.click(screen.getByRole("button", { name: "Xoá vĩnh viễn" }))
}

function confirmButton() {
  const dialog = screen.getByRole("dialog")
  const buttons = dialog.querySelectorAll("button")
  return Array.from(buttons).find((b) => b.textContent === "Xoá vĩnh viễn") as HTMLButtonElement
}

describe("Hộp thoại xoá vĩnh viễn dự án", () => {
  beforeEach(() => {
    mocks.remove.mockReset()
    vi.mocked(toast.error).mockClear()
  })
  afterEach(cleanup)

  it("nút Xoá bị khoá tới khi gõ đúng tên (thừa khoảng trắng vẫn khớp)", () => {
    open()
    const input = screen.getByRole("textbox")
    expect(confirmButton().disabled).toBe(true)
    fireEvent.change(input, { target: { value: "Dự án B" } })
    expect(confirmButton().disabled).toBe(true)
    fireEvent.change(input, { target: { value: "  Dự án A " } })
    expect(confirmButton().disabled).toBe(false)
  })

  it("bấm Xoá gọi API đúng một lần với tên đã gõ", async () => {
    mocks.remove.mockResolvedValue(undefined)
    open()
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Dự án A" } })
    fireEvent.click(confirmButton())
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledTimes(1))
    expect(mocks.remove).toHaveBeenCalledWith("Dự án A")
  })

  it("lỗi thì báo lỗi và hộp thoại vẫn mở", async () => {
    mocks.remove.mockRejectedValue(new ApiError(409, "Hệ thống đang bận"))
    open()
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Dự án A" } })
    fireEvent.click(confirmButton())
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Hệ thống đang bận"))
    expect(screen.getByRole("dialog")).toBeTruthy()
  })

  it("giải thích chỉ xoá khỏi app, Sheet và issue GitHub vẫn còn", () => {
    open()
    expect(
      screen.getByText(/Chỉ xoá khỏi app, file Google Sheet và issue GitHub vẫn còn/),
    ).toBeTruthy()
  })
})

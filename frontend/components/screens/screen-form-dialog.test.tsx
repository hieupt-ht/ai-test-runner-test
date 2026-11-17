import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ScreenFormDialog } from "@/components/screens/screen-form-dialog"
import type { Screen } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mutateAsync = vi.fn()
vi.mock("@/lib/use-project-data", () => ({
  useSaveScreen: () => ({ mutateAsync, isPending: false }),
}))

const existing = {
  id: "SC-0001",
  name: "Đăng nhập",
  description: "",
  route: "/login",
  code_paths: [],
  created_at: "2026-11-17T00:00:00Z",
  dev_owner: "nguyenvana",
} satisfies Screen

function openDialog(screenToEdit?: Screen) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ScreenFormDialog
          projectId="P1"
          screen={screenToEdit}
          trigger={<button type="button" />}
          triggerLabel="Mở"
        />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByText("Mở"))
}

describe("ScreenFormDialog – dev phụ trách", () => {
  afterEach(() => {
    cleanup()
    mutateAsync.mockReset()
  })

  it("hiện sẵn tên dev khi sửa màn hình", () => {
    openDialog(existing)
    expect(screen.getByLabelText("Dev phụ trách (tên GitHub)")).toHaveValue("nguyenvana")
  })

  it("gửi dev_owner lên API khi lưu", async () => {
    mutateAsync.mockResolvedValue(existing)
    openDialog(existing)
    fireEvent.change(screen.getByLabelText("Dev phụ trách (tên GitHub)"), {
      target: { value: "tran-b" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({ dev_owner: "tran-b" })
  })

  it("chặn lưu khi tên GitHub sai và không gọi API", () => {
    openDialog(existing)
    fireEvent.change(screen.getByLabelText("Dev phụ trách (tên GitHub)"), {
      target: { value: "a b" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
    expect(screen.getByText("Tên GitHub chỉ gồm chữ, số và dấu gạch ngang")).toBeInTheDocument()
    expect(mutateAsync).not.toHaveBeenCalled()
  })

  it("cho bỏ trống và tự bỏ @ ở đầu", async () => {
    mutateAsync.mockResolvedValue(existing)
    openDialog(existing)
    fireEvent.change(screen.getByLabelText("Dev phụ trách (tên GitHub)"), {
      target: { value: "@abc" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({ dev_owner: "abc" })
  })
})

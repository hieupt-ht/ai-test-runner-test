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

vi.mock("@/lib/use-modules", () => ({
  useModules: () => ({ data: [{ id: "MD-0001", name: "Tài khoản" }] }),
}))

vi.mock("@/lib/use-projects", () => ({
  useProject: () => ({ data: { storage: "cloudinary" } }),
}))

const existingMedia = {
  kind: "image" as const,
  public_id: "guide/a",
  url: "https://res.cloudinary.com/demo/image/upload/a.png",
  note: "",
}
const fakeMedia = { ...existingMedia, public_id: "guide/fake" }

// Ô chọn ảnh giả: hai nút để giả lập thêm ảnh và đang tải
vi.mock("@/components/media/media-picker", () => ({
  MediaPicker: ({
    value,
    onChange,
    onBusyChange,
  }: {
    value: unknown[]
    onChange: (next: unknown[]) => void
    onBusyChange?: (busy: boolean) => void
  }) => (
    <div>
      <button type="button" onClick={() => onChange([...value, fakeMedia])}>
        Thêm ảnh giả
      </button>
      <button type="button" onClick={() => onBusyChange?.(true)}>
        Đang tải giả
      </button>
    </div>
  ),
}))

const existing = {
  id: "SC-0001",
  name: "Đăng nhập",
  description: "",
  route: "/login",
  code_paths: [],
  created_at: "2026-11-17T00:00:00Z",
  dev_owner: "nguyenvana",
  media: [existingMedia],
  module_id: "",
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

describe("ScreenFormDialog – ảnh/video", () => {
  afterEach(() => {
    cleanup()
    mutateAsync.mockReset()
  })

  it("hiện ảnh sẵn có khi sửa và gửi media khi lưu", async () => {
    mutateAsync.mockResolvedValue(existing)
    openDialog(existing)
    fireEvent.click(screen.getByText("Thêm ảnh giả"))
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({ media: [existingMedia, fakeMedia] })
  })

  it("khoá nút Lưu khi đang tải ảnh lên", () => {
    openDialog(existing)
    fireEvent.click(screen.getByText("Đang tải giả"))
    expect(screen.getByRole("button", { name: "Lưu" })).toBeDisabled()
  })
})

describe("ScreenFormDialog – mở lại sau khi huỷ", () => {
  afterEach(() => {
    cleanup()
    mutateAsync.mockReset()
  })

  it("thêm ảnh rồi Huỷ thì lần mở sau không còn ảnh đó, Lưu không gửi ảnh thừa", async () => {
    mutateAsync.mockResolvedValue(existing)
    openDialog(existing)
    fireEvent.click(screen.getByText("Thêm ảnh giả"))
    fireEvent.click(screen.getByRole("button", { name: "Huỷ" }))
    fireEvent.click(screen.getByText("Mở"))
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({ media: [existingMedia] })
  })
})

describe("ScreenFormDialog – module", () => {
  afterEach(() => {
    cleanup()
    mutateAsync.mockReset()
  })

  it("có lựa chọn Chưa phân module và gửi module_id đã chọn", async () => {
    mutateAsync.mockResolvedValue(existing)
    openDialog(existing)
    const select = screen.getByLabelText("Module")
    expect(select).toHaveValue("")
    expect(screen.getByRole("option", { name: "Chưa phân module" })).toBeInTheDocument()

    fireEvent.change(select, { target: { value: "MD-0001" } })
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }))

    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0]).toMatchObject({ module_id: "MD-0001" })
  })

  it("hiện sẵn module hiện tại khi sửa màn hình", () => {
    openDialog({ ...existing, module_id: "MD-0001" })
    expect(screen.getByLabelText("Module")).toHaveValue("MD-0001")
  })
})

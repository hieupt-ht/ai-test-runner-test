import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ImportDialog } from "@/components/test-cases/import-dialog"
import { ApiError } from "@/lib/api/client"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  preview: vi.fn(),
  importCases: vi.fn(),
  toastSuccess: vi.fn(),
}))

vi.mock("sonner", () => ({ toast: { success: mocks.toastSuccess, error: vi.fn() } }))
vi.mock("@/lib/use-case-import", () => ({
  templateUrl: (projectId: string) => `/api/projects/${projectId}/test-cases/import/template`,
  usePreviewImport: () => ({ mutateAsync: mocks.preview, isPending: false }),
  useImportCases: () => ({ mutateAsync: mocks.importCases, isPending: false }),
}))

function parsed(group: string, screenId: string, row: number) {
  return {
    group,
    row,
    screen_id: screenId,
    screen_name: `Màn ${screenId}`,
    title: `Case ${group}`,
    step_count: 4,
    content: {},
  }
}

// 12 case: 5 case x 4 bước + 7 case x 3 bước = 41 bước, trải trên 3 màn hình
function okResult() {
  const cases = Array.from({ length: 12 }, (_, i) => parsed(`G${i + 1}`, `SC-000${(i % 3) + 1}`, i + 2))
  cases.forEach((c, i) => (c.step_count = i < 5 ? 4 : 3))
  return { cases, errors: [], warnings: [] }
}

function renderDialog(onOpenChange = vi.fn()) {
  render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <ImportDialog projectId="p1" open onOpenChange={onOpenChange} />
    </NextIntlClientProvider>,
  )
  return onOpenChange
}

async function pickFile() {
  const file = new File(["x"], "cases.xlsx")
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [file] } })
  return file
}

describe("Hộp thoại nhập test case từ Excel", () => {
  beforeEach(() => {
    mocks.preview.mockReset()
    mocks.importCases.mockReset()
    mocks.toastSuccess.mockReset()
  })
  afterEach(cleanup)

  it("chọn file thì xem trước và hiện tóm tắt cùng bảng", async () => {
    mocks.preview.mockResolvedValue(okResult())
    renderDialog()
    const file = await pickFile()
    expect(mocks.preview).toHaveBeenCalledWith(file)
    expect(await screen.findByText("Xem trước: 12 case · 41 bước · 3 màn hình")).toBeInTheDocument()
    for (const name of ["Mã nhóm", "Màn hình", "Tiêu đề", "Số bước"]) {
      expect(screen.getByRole("columnheader", { name })).toBeInTheDocument()
    }
    expect(screen.getByRole("button", { name: "Nhập 12 case" })).toBeEnabled()
  })

  it("có lỗi thì liệt kê theo dòng và khóa nút Nhập", async () => {
    const result = okResult()
    result.errors = [
      { row: 9, column: "Tiêu đề", message: "Không được để trống" },
      { row: 7, column: "Kết quả mong đợi", message: "Không được để trống" },
      { row: null, message: "File không có test case nào" },
    ] as never
    mocks.preview.mockResolvedValue(result)
    renderDialog()
    await pickFile()
    expect(await screen.findByText("Dòng 7 · Kết quả mong đợi: Không được để trống")).toBeInTheDocument()
    const items = screen.getAllByRole("listitem").map((li) => li.textContent)
    expect(items.indexOf("Dòng 7 · Kết quả mong đợi: Không được để trống")).toBeLessThan(
      items.indexOf("Dòng 9 · Tiêu đề: Không được để trống"),
    )
    expect(screen.getByText("File không có test case nào")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Nhập 12 case" })).toBeDisabled()
  })

  it("lỗi 422 từ backend cũng hiện từng dòng", async () => {
    mocks.preview.mockRejectedValue(
      new ApiError(422, "x", { errors: [{ row: 3, column: "Mã nhóm", message: "Thiếu" }] }),
    )
    renderDialog()
    await pickFile()
    expect(await screen.findByText("Dòng 3 · Mã nhóm: Thiếu")).toBeInTheDocument()
  })

  it("chỉ có cảnh báo thì vẫn nhập được", async () => {
    const result = okResult()
    result.warnings = [{ row: 5, column: null, message: "Ảnh bị bỏ qua" }] as never
    mocks.preview.mockResolvedValue(result)
    renderDialog()
    await pickFile()
    expect(await screen.findByText("Dòng 5: Ảnh bị bỏ qua")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Nhập 12 case" })).toBeEnabled()
  })

  it("bấm Nhập thì gửi cùng file, báo thành công và đóng hộp thoại", async () => {
    mocks.preview.mockResolvedValue(okResult())
    mocks.importCases.mockResolvedValue({ created: Array.from({ length: 12 }, (_, i) => `TC-${i}`) })
    const onOpenChange = renderDialog()
    const file = await pickFile()
    fireEvent.click(await screen.findByRole("button", { name: "Nhập 12 case" }))
    await waitFor(() => expect(mocks.importCases).toHaveBeenCalledWith(file))
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Đã nhập 12 case")
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("lỗi 409 khi nhập thì hiện câu của backend và vẫn mở", async () => {
    mocks.preview.mockResolvedValue(okResult())
    mocks.importCases.mockRejectedValue(new ApiError(409, "Dự án đang có lượt nhập khác", undefined))
    const onOpenChange = renderDialog()
    await pickFile()
    fireEvent.click(await screen.findByRole("button", { name: "Nhập 12 case" }))
    expect(await screen.findByText("Dự án đang có lượt nhập khác")).toBeInTheDocument()
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it("lỗi 503 khi xem trước thì hiện câu của backend", async () => {
    mocks.preview.mockRejectedValue(new ApiError(503, "Google đang bận", undefined))
    renderDialog()
    await pickFile()
    expect(await screen.findByText("Google đang bận")).toBeInTheDocument()
  })

  it("link Tải file mẫu trỏ đúng địa chỉ", () => {
    renderDialog()
    expect(screen.getByRole("link", { name: "Tải file mẫu" })).toHaveAttribute(
      "href",
      "/api/projects/p1/test-cases/import/template",
    )
  })

  it("chọn lại file thì xem trước lại", async () => {
    mocks.preview.mockResolvedValue(okResult())
    renderDialog()
    await pickFile()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(["y"], "b.xlsx")] } })
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledTimes(2))
  })

  it("chọn xong thì xoá giá trị ô chọn file để chọn lại đúng file đó vẫn nhận", async () => {
    mocks.preview.mockResolvedValue(okResult())
    renderDialog()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const resetValue = vi.fn()
    Object.defineProperty(input, "value", { set: resetValue, get: () => "" })
    await pickFile()
    expect(resetValue).toHaveBeenCalledWith("")
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledWith(expect.any(File)))
  })

  it("trước khi chọn file nút Nhập không ghi số case", () => {
    renderDialog()
    expect(screen.getByRole("button", { name: "Nhập" })).toBeDisabled()
  })

  it("xem trước của file cũ về chậm thì bị bỏ qua", async () => {
    let resolveFirst: (value: unknown) => void = () => {}
    mocks.preview.mockReturnValueOnce(new Promise((resolve) => (resolveFirst = resolve)))
    const second = { ...okResult(), cases: okResult().cases.slice(0, 2) }
    mocks.preview.mockResolvedValueOnce(second)
    renderDialog()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(["a"], "a.xlsx")] } })
    fireEvent.change(input, { target: { files: [new File(["b"], "b.xlsx")] } })
    expect(await screen.findByRole("button", { name: "Nhập 2 case" })).toBeEnabled()
    resolveFirst(okResult())
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.getByRole("button", { name: "Nhập 2 case" })).toBeInTheDocument()
  })

  it("đóng rồi mở lại thì xem trước cũ biến mất", async () => {
    mocks.preview.mockResolvedValue(okResult())
    const view = render(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ImportDialog projectId="p1" open onOpenChange={() => {}} />
      </NextIntlClientProvider>,
    )
    await pickFile()
    await screen.findByRole("button", { name: "Nhập 12 case" })
    fireEvent.click(screen.getByRole("button", { name: "Đóng" }))
    view.rerender(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ImportDialog projectId="p1" open={false} onOpenChange={() => {}} />
      </NextIntlClientProvider>,
    )
    view.rerender(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ImportDialog projectId="p1" open onOpenChange={() => {}} />
      </NextIntlClientProvider>,
    )
    expect(screen.getByRole("button", { name: "Nhập" })).toBeDisabled()
    expect(screen.queryByText(/Xem trước:/)).not.toBeInTheDocument()
  })
})

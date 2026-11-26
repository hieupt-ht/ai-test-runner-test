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
  user: { email: "lead@x.com", role: "QA_LEAD" } as { email: string; role: string },
  modules: [] as unknown[],
  screens: [] as unknown[],
  assignments: [] as unknown[],
}))

vi.mock("@/lib/use-me", () => ({ useMe: () => ({ user: mocks.user, isLoading: false }) }))
vi.mock("@/lib/use-modules", () => ({ useModules: () => ({ data: mocks.modules }) }))
vi.mock("@/lib/use-project-data", () => ({
  useScreens: () => ({ data: mocks.screens }),
  useAssignments: () => ({ data: mocks.assignments }),
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

/** Chọn module trước (bắt buộc); mặc định "Không theo module (như cũ)". */
function chooseModule(value = "none") {
  fireEvent.change(screen.getByLabelText("Module"), { target: { value } })
}

async function pickFile(moduleValue: string | null = "none") {
  if (moduleValue !== null) chooseModule(moduleValue)
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
    mocks.user = { email: "lead@x.com", role: "QA_LEAD" }
    mocks.modules = []
    mocks.screens = []
    mocks.assignments = []
  })
  afterEach(cleanup)

  it("chọn file thì xem trước và hiện tóm tắt cùng bảng", async () => {
    mocks.preview.mockResolvedValue(okResult())
    renderDialog()
    const file = await pickFile()
    expect(mocks.preview).toHaveBeenCalledWith({ file, moduleId: "" })
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
    await waitFor(() => expect(mocks.importCases).toHaveBeenCalledWith({ file, moduleId: "" }))
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
    await waitFor(() =>
      expect(mocks.preview).toHaveBeenCalledWith({ file: expect.any(File), moduleId: "" }),
    )
  })

  it("hiện tên file đã chọn dưới ô chọn file", async () => {
    mocks.preview.mockResolvedValue(okResult())
    renderDialog()
    await pickFile()
    expect(await screen.findByText("cases.xlsx")).toBeInTheDocument()
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
    expect(screen.queryByText("cases.xlsx")).not.toBeInTheDocument()
  })
})


describe("Nhập theo module", () => {
  beforeEach(() => {
    mocks.preview.mockReset()
    mocks.importCases.mockReset()
    mocks.user = { email: "lead@x.com", role: "QA_LEAD" }
    mocks.modules = [
      { id: "MD-0001", name: "Tài khoản", workers: [{ email: "an@x.com", name: "An" }] },
      { id: "MD-0002", name: "Giỏ hàng", workers: [] },
    ]
    mocks.screens = []
    mocks.assignments = []
  })
  afterEach(cleanup)

  it("requires module choice before upload", () => {
    renderDialog()

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input).toBeDisabled()
    expect(screen.getByText("Hãy chọn module trước khi chọn file")).toBeInTheDocument()

    chooseModule("MD-0001")
    expect(input).toBeEnabled()
  })

  it("sends module_id with file", async () => {
    mocks.preview.mockResolvedValue(okResult())
    mocks.importCases.mockResolvedValue({ created: ["TC-1"] })
    renderDialog()
    const file = await pickFile("MD-0001")

    expect(mocks.preview).toHaveBeenCalledWith({ file, moduleId: "MD-0001" })
    fireEvent.click(await screen.findByRole("button", { name: "Nhập 12 case" }))
    await waitFor(() =>
      expect(mocks.importCases).toHaveBeenCalledWith({ file, moduleId: "MD-0001" }),
    )
  })

  it("changing module after preview previews again", async () => {
    mocks.preview.mockResolvedValue(okResult())
    renderDialog()
    const file = await pickFile("MD-0001")
    await screen.findByRole("button", { name: "Nhập 12 case" })

    chooseModule("MD-0002")

    await waitFor(() =>
      expect(mocks.preview).toHaveBeenLastCalledWith({ file, moduleId: "MD-0002" }),
    )
    expect(mocks.preview).toHaveBeenCalledTimes(2)
  })

  it("shows new screens notice and allows import", async () => {
    mocks.preview.mockResolvedValue({
      ...okResult(),
      new_screens: ["Đăng ký", "Hồ sơ"],
    })
    renderDialog()
    await pickFile("MD-0001")

    expect(await screen.findByText("Sẽ tạo mới 2 màn hình: Đăng ký, Hồ sơ")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Nhập 12 case" })).toBeEnabled()
  })

  it("qa sees every module plus the old option", () => {
    renderDialog()

    const names = screen.getAllByRole("option").map((option) => option.textContent)
    expect(names).toEqual(["Chọn module", "Không theo module (như cũ)", "Tài khoản", "Giỏ hàng"])
  })

  it("tester only sees own modules", () => {
    mocks.user = { email: "an@x.com", role: "TESTER" }
    renderDialog()

    const names = screen.getAllByRole("option").map((option) => option.textContent)
    expect(names).toEqual(["Chọn module", "Tài khoản"])
  })

  it("tester with loose screen assignments also sees the old option", () => {
    mocks.user = { email: "an@x.com", role: "TESTER" }
    mocks.screens = [{ id: "SC-0009", module_id: "" }]
    mocks.assignments = [{ screen_id: "SC-0009", assignee_email: "an@x.com" }]
    renderDialog()

    const names = screen.getAllByRole("option").map((option) => option.textContent)
    expect(names).toEqual(["Chọn module", "Không theo module (như cũ)", "Tài khoản"])
  })
})

describe("Đổi module về chưa chọn", () => {
  afterEach(cleanup)

  it("khoá nút Nhập và bỏ bản xem trước cũ", async () => {
    mocks.preview.mockReset()
    mocks.modules = [{ id: "MD-0001", name: "Tài khoản", workers: [] }]
    mocks.user = { email: "lead@x.com", role: "QA_LEAD" }
    mocks.preview.mockResolvedValue(okResult())
    renderDialog()
    await pickFile("MD-0001")
    await screen.findByRole("button", { name: "Nhập 12 case" })

    chooseModule("")

    expect(screen.getByRole("button", { name: "Nhập" })).toBeDisabled()
    expect(screen.queryByText(/Xem trước:/)).not.toBeInTheDocument()
  })
})

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { toast } from "sonner"

import { ManualRunPanel } from "@/components/test-cases/manual-run-panel"
import type { TestCase } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const submitMock = vi.hoisted(() => vi.fn())

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn() } }))
vi.mock("@/lib/use-manual-result", () => ({
  useSubmitManualResult: () => ({ mutateAsync: submitMock, isPending: false }),
}))
// Ô chọn ảnh thật cần mạng: ở đây chỉ cần biết mục đích tải lên và giả lập "đang tải".
vi.mock("@/components/media/media-picker", () => ({
  MediaPicker: ({
    onBusyChange,
    onChange,
    purpose,
  }: {
    onBusyChange?: (busy: boolean) => void
    onChange?: (next: unknown[]) => void
    purpose?: string
  }) => (
    <>
      <button type="button" data-purpose={purpose} onClick={() => onBusyChange?.(true)}>
        giả-lập-tải-lên
      </button>
      <button
        type="button"
        onClick={() =>
          onChange?.([{ kind: "image", url: "https://x/a.png", public_id: "ai-test-runner/p/evidence/a" }])
        }
      >
        giả-lập-thêm-ảnh
      </button>
    </>
  ),
}))

const TEST_CASE = {
  id: "TC-000001",
  version: 3,
  steps: [
    { action: "Mở /login", expected: "", guide_media: [] },
    { action: "Nhập sai mật khẩu", expected: "Báo lỗi", guide_media: [] },
  ],
} as unknown as TestCase

function renderPanel(props: Partial<Parameters<typeof ManualRunPanel>[0]> = {}) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ManualRunPanel
          projectId="PRJ-0001"
          storage="cloudinary"
          testCase={TEST_CASE}
          {...props}
        />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
}

const stepRadio = (step: number, label: "Đạt" | "Không đạt" | "Bỏ qua") =>
  screen.getByRole("radio", { name: `Bước ${step}: ${label}` })
const submitButton = () => screen.getByRole("button", { name: "Gửi kết quả" })

function answerAll(status: "Đạt" | "Không đạt" = "Đạt") {
  fireEvent.click(stepRadio(1, status))
  fireEvent.click(stepRadio(2, status))
}

function typeEnvironment(value = "Chrome 130 / Windows 11") {
  fireEvent.change(screen.getByLabelText("Môi trường"), { target: { value } })
}

describe("ManualRunPanel", () => {
  beforeEach(() => {
    submitMock.mockReset()
    submitMock.mockResolvedValue({ run_id: "RUN-0001", case: TEST_CASE })
    try {
      localStorage.clear()
    } catch {
      /* trình duyệt chặn lưu trữ thì bỏ qua */
    }
  })
  afterEach(cleanup)

  it("nút Gửi khoá khi chưa chọn kết quả cho mọi bước", () => {
    renderPanel()
    typeEnvironment()
    fireEvent.click(stepRadio(1, "Đạt"))
    expect(submitButton()).toBeDisabled()
    fireEvent.click(stepRadio(2, "Đạt"))
    expect(submitButton()).toBeEnabled()
  })

  it("nút Gửi khoá khi chưa nhập Môi trường", () => {
    renderPanel()
    answerAll()
    expect(submitButton()).toBeDisabled()
    typeEnvironment("  ")
    expect(submitButton()).toBeDisabled()
    typeEnvironment()
    expect(submitButton()).toBeEnabled()
  })

  it("chọn Không đạt ở bước 2 thì gợi ý Fail và bước lỗi = 2", () => {
    renderPanel()
    fireEvent.click(stepRadio(1, "Đạt"))
    fireEvent.click(stepRadio(2, "Không đạt"))
    expect(screen.getByRole("radio", { name: "Fail" })).toBeChecked()
    expect(screen.getByLabelText("Bước lỗi")).toHaveValue("2")
  })

  it("đổi lại Đạt thì bỏ gợi ý bước lỗi", () => {
    renderPanel()
    fireEvent.click(stepRadio(1, "Đạt"))
    fireEvent.click(stepRadio(2, "Không đạt"))
    fireEvent.click(stepRadio(2, "Đạt"))
    // Không còn bước nào Không đạt: ô bước lỗi không kẹt ở 2 và kết quả gợi ý quay về Pass
    expect(screen.queryByLabelText("Bước lỗi")).not.toBeInTheDocument()
    expect(screen.getByRole("radio", { name: "Pass" })).toBeChecked()
  })

  it("đổi bước Không đạt đầu tiên thì bước lỗi quay về bước Không đạt còn lại", () => {
    renderPanel()
    fireEvent.click(stepRadio(1, "Không đạt"))
    fireEvent.click(stepRadio(2, "Không đạt"))
    expect(screen.getByLabelText("Bước lỗi")).toHaveValue("1")
    fireEvent.click(stepRadio(1, "Đạt"))
    expect(screen.getByLabelText("Bước lỗi")).toHaveValue("2")
  })

  it("Fail thì bắt buộc mô tả lỗi", () => {
    renderPanel()
    typeEnvironment()
    fireEvent.click(stepRadio(1, "Đạt"))
    fireEvent.click(stepRadio(2, "Không đạt"))
    fireEvent.click(screen.getAllByRole("button", { name: "giả-lập-thêm-ảnh" })[0])
    expect(submitButton()).toBeDisabled()
    fireEvent.change(screen.getByLabelText("Mô tả lỗi"), { target: { value: "Không báo lỗi" } })
    expect(submitButton()).toBeEnabled()
  })

  it("Fail không có ảnh vẫn gửi được, chỉ hiện nhắc", () => {
    renderPanel()
    typeEnvironment()
    fireEvent.click(stepRadio(1, "Đạt"))
    fireEvent.click(stepRadio(2, "Không đạt"))
    fireEvent.change(screen.getByLabelText("Mô tả lỗi"), { target: { value: "Không báo lỗi" } })
    expect(submitButton()).toBeEnabled()
    expect(screen.getByText("Nên thêm ảnh hoặc video để dev dễ tìm lỗi.")).toBeInTheDocument()

    fireEvent.click(screen.getAllByRole("button", { name: "giả-lập-thêm-ảnh" })[0])
    expect(submitButton()).toBeEnabled()
    expect(screen.queryByText("Nên thêm ảnh hoặc video để dev dễ tìm lỗi.")).not.toBeInTheDocument()
  })

  it("Giao cho mặc định là dev phụ trách màn hình", () => {
    renderPanel({ defaultAssignee: "nguyenvana" })
    expect(screen.getByLabelText("Giao cho (GitHub)")).toHaveValue("nguyenvana")
  })

  it("tên GitHub sai thì khoá nút Gửi", () => {
    renderPanel()
    typeEnvironment()
    answerAll()
    fireEvent.change(screen.getByLabelText("Giao cho (GitHub)"), { target: { value: "-sai tên" } })
    expect(submitButton()).toBeDisabled()
  })

  it("khoá nút Gửi khi ô chọn ảnh báo đang tải", () => {
    renderPanel()
    typeEnvironment()
    answerAll()
    expect(submitButton()).toBeEnabled()
    fireEvent.click(screen.getAllByRole("button", { name: "giả-lập-tải-lên" })[0])
    expect(submitButton()).toBeDisabled()
  })

  it("mọi ô chọn ảnh tải lên với mục đích bằng chứng", () => {
    renderPanel()
    for (const picker of screen.getAllByRole("button", { name: "giả-lập-tải-lên" })) {
      expect(picker).toHaveAttribute("data-purpose", "evidence")
    }
  })

  it("gửi đúng body lên backend", async () => {
    const onDone = vi.fn()
    renderPanel({ onDone })
    typeEnvironment()
    answerAll()
    fireEvent.change(screen.getByLabelText("Phiên bản build (không bắt buộc)"), {
      target: { value: "1.2.3" },
    })
    fireEvent.click(submitButton())

    await waitFor(() => expect(submitMock).toHaveBeenCalledTimes(1))
    expect(submitMock).toHaveBeenCalledWith({
      status: "PASS",
      step_results: [
        { step_no: 1, status: "PASS", actual: "" },
        { step_no: 2, status: "PASS", actual: "" },
      ],
      actual_result: "",
      reason: "",
      failed_step: null,
      evidence: { video: null, screenshots: [] },
      environment: "Chrome 130 / Windows 11",
      build_version: "1.2.3",
      assignee: "",
      version: 3,
    })
    await waitFor(() => expect(onDone).toHaveBeenCalledWith({ run_id: "RUN-0001", case: TEST_CASE }))
    expect(toast.success).toHaveBeenCalled()
  })

  it("Fail gửi kèm bước lỗi, mô tả lỗi và người được giao (bỏ @ ở đầu)", async () => {
    renderPanel({ defaultAssignee: "nguyenvana" })
    typeEnvironment()
    fireEvent.click(stepRadio(1, "Đạt"))
    fireEvent.click(stepRadio(2, "Không đạt"))
    fireEvent.change(screen.getByLabelText("Mô tả lỗi"), { target: { value: "Không báo lỗi" } })
    fireEvent.click(screen.getAllByRole("button", { name: "giả-lập-thêm-ảnh" })[0])
    fireEvent.change(screen.getByLabelText("Giao cho (GitHub)"), { target: { value: "@tran-b" } })
    fireEvent.click(submitButton())

    await waitFor(() => expect(submitMock).toHaveBeenCalledTimes(1))
    expect(submitMock).toHaveBeenCalledWith(
      expect.objectContaining({
        status: "FAIL",
        reason: "Không báo lỗi",
        failed_step: 2,
        assignee: "tran-b",
      }),
    )
  })

  it("nhớ Môi trường lần trước ở trình duyệt", async () => {
    const first = renderPanel()
    typeEnvironment("Firefox 131")
    answerAll()
    fireEvent.click(submitButton())
    await waitFor(() => expect(submitMock).toHaveBeenCalled())
    first.unmount()

    renderPanel()
    expect(screen.getByLabelText("Môi trường")).toHaveValue("Firefox 131")
  })

  it("gửi lỗi thì báo bằng thông báo nổi và giữ nguyên những gì đã nhập", async () => {
    submitMock.mockRejectedValue(new Error("Case vừa được sửa, hãy tải lại"))
    renderPanel()
    typeEnvironment()
    answerAll()
    fireEvent.click(submitButton())

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Case vừa được sửa, hãy tải lại"))
    expect(screen.getByLabelText("Môi trường")).toHaveValue("Chrome 130 / Windows 11")
    expect(stepRadio(1, "Đạt")).toBeChecked()
  })

  it("gửi xong thì làm trống các bước để chạy lần sau", async () => {
    renderPanel()
    typeEnvironment()
    answerAll()
    fireEvent.click(submitButton())
    await waitFor(() => expect(stepRadio(1, "Đạt")).not.toBeChecked())
    expect(screen.getByLabelText("Môi trường")).toHaveValue("Chrome 130 / Windows 11")
  })
})

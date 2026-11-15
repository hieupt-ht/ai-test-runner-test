import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import ResultsPage from "@/app/(app)/projects/[projectId]/results/page"
import type { ResultItem } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  searchParams: "screen=SC-login",
  useResults: vi.fn(),
  useRequestRerun: vi.fn(),
  useMe: vi.fn(),
  mutate: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock("@/lib/use-project-id", () => ({ useProjectId: () => "p1" }))
vi.mock("@/lib/use-results", () => ({
  useResults: mocks.useResults,
  useRequestRerun: mocks.useRequestRerun,
}))
vi.mock("@/lib/use-me", () => ({ useMe: mocks.useMe }))
vi.mock("sonner", () => ({ toast: { success: mocks.toastSuccess, error: mocks.toastError } }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  useSearchParams: () => new URLSearchParams(mocks.searchParams),
}))

const results: ResultItem[] = [
  {
    case_id: "TC-1",
    case_title: "Đăng nhập thành công",
    screen_id: "SC-login",
    screen_name: "Đăng nhập",
    status: "FAIL",
    reason: "Sai mật khẩu vẫn đăng nhập được",
    failed_step: 2,
    evidence: "javascript:alert(1)",
    run_id: "run-1",
    finished_at: "2026-11-14T10:00:00Z",
  },
  {
    case_id: "TC-2",
    case_title: "Trang chủ tải được",
    screen_id: "SC-login",
    screen_name: "Đăng nhập",
    status: "PASS",
    reason: "Đúng kết quả mong đợi",
    failed_step: null,
    evidence: "https://example.com/evidence.png",
    run_id: "run-2",
    finished_at: "2026-11-14T11:00:00Z",
  },
]

const homeResult: ResultItem = {
  ...results[1],
  case_id: "TC-3",
  screen_id: "SC-home",
  screen_name: "Trang chủ",
}

const blockedResult: ResultItem = {
  ...results[1],
  case_id: "TC-4",
  screen_id: "SC-checkout",
  screen_name: "Thanh toán",
  status: "BLOCKED",
}

function renderPage() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <ResultsPage />
    </NextIntlClientProvider>,
  )
}

describe("ResultsPage", () => {
  beforeEach(() => {
    mocks.searchParams = "screen=SC-login"
    mocks.useMe.mockReturnValue({ user: { role: "QA_LEAD" }, isLoading: false })
    mocks.useRequestRerun.mockReturnValue({ mutate: mocks.mutate, isPending: false, variables: undefined })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("hiện trạng thái, lý do, bước lỗi và chỉ tạo link an toàn", () => {
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
    const { container } = renderPage()

    expect(screen.getByRole("button", { name: /FAIL: 1/ })).toBeInTheDocument()
    expect(screen.getByText("Sai mật khẩu vẫn đăng nhập được")).toBeInTheDocument()
    expect(screen.getByText("Bước lỗi: 2")).toBeInTheDocument()
    expect(container.querySelector('a[href^="javascript:"]')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /PASS: 1/ }))
    expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute(
      "href",
      "https://example.com/evidence.png",
    )
  })

  it("lọc trạng thái trong dữ liệu của màn hình", () => {
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
    renderPage()

    fireEvent.change(screen.getByRole("combobox", { name: "Lọc trạng thái" }), {
      target: { value: "PASS" },
    })
    expect(mocks.useResults).toHaveBeenLastCalledWith("p1", undefined, "SC-login")
    expect(screen.getByRole("button", { name: /PASS: 1/ })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /FAIL:/ })).not.toBeInTheDocument()
  })

  it("hiện trạng thái rỗng khi chưa có kết quả", () => {
    mocks.useResults.mockReturnValue({ data: [], isLoading: false, isError: false })
    renderPage()

    expect(screen.getByText("Chưa có kết quả test")).toBeInTheDocument()
  })

  it("tính số kết quả và mở FAIL/BLOCKED nhưng thu PASS mặc định", () => {
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
    renderPage()

    expect(screen.getByText("PASS: 1")).toBeInTheDocument()
    expect(screen.getByText("FAIL: 1")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /PASS: 1/ })).toHaveAttribute("aria-expanded", "false")
    expect(screen.getByRole("button", { name: /FAIL: 1/ })).toHaveAttribute("aria-expanded", "true")
  })

  it("bấm tiêu đề nhóm để đổi trạng thái thu mở", () => {
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
    renderPage()

    fireEvent.click(screen.getByRole("button", { name: /FAIL: 1/ }))
    expect(screen.getByRole("button", { name: /FAIL: 1/ })).toHaveAttribute("aria-expanded", "false")
  })

  it("chỉ hiện nhóm được lọc", () => {
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
    renderPage()
    fireEvent.change(screen.getByRole("combobox", { name: "Lọc trạng thái" }), {
      target: { value: "FAIL" },
    })

    expect(screen.getByRole("button", { name: /FAIL:/ })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /PASS:/ })).not.toBeInTheDocument()
  })

  it("không có screen thì hiện danh sách màn hình và ẩn bảng case", () => {
    mocks.searchParams = ""
    mocks.useResults.mockReturnValue({
      data: [...results, homeResult, blockedResult],
      isLoading: false,
      isError: false,
    })

    renderPage()

    expect(screen.getByRole("button", { name: /Đăng nhập/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Trang chủ/ })).toBeInTheDocument()
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(mocks.useResults).toHaveBeenLastCalledWith("p1", undefined, undefined)
  })

  it("có screen thì hiện bảng case và ẩn danh sách màn hình", () => {
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })

    renderPage()

    expect(screen.getByRole("heading", { name: "Đăng nhập" })).toBeInTheDocument()
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Trang chủ/ })).not.toBeInTheDocument()
    expect(mocks.useResults).toHaveBeenLastCalledWith("p1", undefined, "SC-login")
  })

  it("bấm card màn hình thì thêm screen vào URL", () => {
    mocks.searchParams = ""
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
    renderPage()

    fireEvent.click(screen.getByRole("button", { name: /Đăng nhập/ }))

    expect(mocks.push).toHaveBeenCalledWith("/projects/p1/results?screen=SC-login")
  })

  it("bấm Tất cả màn hình thì xóa screen khỏi URL", () => {
    mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
    renderPage()

    fireEvent.click(screen.getByRole("button", { name: "← Tất cả màn hình" }))

    expect(mocks.push).toHaveBeenCalledWith("/projects/p1/results")
  })

  it("dùng badge đỏ khi có FAIL và badge xanh khi toàn PASS", () => {
    mocks.searchParams = ""
    mocks.useResults.mockReturnValue({
      data: [...results, homeResult, blockedResult],
      isLoading: false,
      isError: false,
    })
    renderPage()

    expect(screen.getByText("✅ 1 · ❌ 1 · ⚠️ 0")).toHaveClass("text-destructive")
    expect(screen.getByText("✅ 1 · ❌ 0 · ⚠️ 0")).toHaveClass("bg-emerald-100")
    expect(screen.getByText("✅ 0 · ❌ 0 · ⚠️ 1")).toHaveClass("bg-amber-100")
  })

  it("không có kết quả ở danh sách thì hiện empty state", () => {
    mocks.searchParams = ""
    mocks.useResults.mockReturnValue({ data: [], isLoading: false, isError: false })
    renderPage()

    expect(screen.getByText("Chưa có kết quả test")).toBeInTheDocument()
  })

  describe("nút Chạy lại", () => {
    it("hiện ở dòng FAIL và ẩn ở dòng PASS", () => {
      mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
      renderPage()

      expect(screen.getAllByRole("button", { name: "Chạy lại" })).toHaveLength(1)
      fireEvent.click(screen.getByRole("button", { name: /PASS: 1/ })) // mở nhóm PASS
      expect(screen.getAllByRole("button", { name: "Chạy lại" })).toHaveLength(1)
    })

    it("hiện ở dòng BLOCKED", () => {
      mocks.useResults.mockReturnValue({
        data: [{ ...blockedResult, screen_id: "SC-login" }],
        isLoading: false,
        isError: false,
      })
      renderPage()

      expect(screen.getByRole("button", { name: "Chạy lại" })).toBeInTheDocument()
    })

    it("ẩn với Tester", () => {
      mocks.useMe.mockReturnValue({ user: { role: "TESTER" }, isLoading: false })
      mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
      renderPage()

      expect(screen.queryByRole("button", { name: "Chạy lại" })).not.toBeInTheDocument()
    })

    it("hiện với Admin", () => {
      mocks.useMe.mockReturnValue({ user: { role: "ADMIN" }, isLoading: false })
      mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
      renderPage()

      expect(screen.getByRole("button", { name: "Chạy lại" })).toBeInTheDocument()
    })

    it("bấm thì gửi đúng mã case", () => {
      mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
      renderPage()

      fireEvent.click(screen.getByRole("button", { name: "Chạy lại" }))

      expect(mocks.useRequestRerun).toHaveBeenCalledWith("p1")
      expect(mocks.mutate).toHaveBeenCalledWith("TC-1", expect.any(Object))
    })

    it("bị khóa và báo đang gửi khi đang tải", () => {
      mocks.useRequestRerun.mockReturnValue({ mutate: mocks.mutate, isPending: true, variables: "TC-1" })
      mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
      renderPage()

      const button = screen.getByRole("button", { name: "Đang gửi..." })
      expect(button).toBeDisabled()
    })

    it("toast thành công khi gửi xong", () => {
      mocks.mutate.mockImplementation((_id: string, options: { onSuccess: () => void }) =>
        options.onSuccess(),
      )
      mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
      renderPage()

      fireEvent.click(screen.getByRole("button", { name: "Chạy lại" }))

      expect(mocks.toastSuccess).toHaveBeenCalledWith("Đã yêu cầu chạy lại. Mở Codex để thực hiện.")
    })

    it("toast lỗi kèm câu báo của API", () => {
      mocks.mutate.mockImplementation((_id: string, options: { onError: (e: Error) => void }) =>
        options.onError(new Error("Chưa cấu hình GitHub")),
      )
      mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
      renderPage()

      fireEvent.click(screen.getByRole("button", { name: "Chạy lại" }))

      expect(mocks.toastError).toHaveBeenCalledWith("Chưa cấu hình GitHub")
    })

    it("toast lỗi dùng câu mặc định khi lỗi không có nội dung", () => {
      mocks.mutate.mockImplementation((_id: string, options: { onError: (e: unknown) => void }) =>
        options.onError(undefined),
      )
      mocks.useResults.mockReturnValue({ data: results, isLoading: false, isError: false })
      renderPage()

      fireEvent.click(screen.getByRole("button", { name: "Chạy lại" }))

      expect(mocks.toastError).toHaveBeenCalledWith("Không yêu cầu được. Thử lại sau.")
    })
  })
})

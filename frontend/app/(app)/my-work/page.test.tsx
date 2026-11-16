import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import MyWorkPage from "@/app/(app)/my-work/page"
import type { MyAssignment } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ items: [] as MyAssignment[] }))
vi.mock("@/lib/use-project-data", () => ({
  useMyAssignments: () => ({ data: mocks.items, isLoading: false }),
}))

const items: MyAssignment[] = [
  {
    assignment_id: "a1", project_id: "p1", project_name: "Dự án A", screen_id: "SCR-1",
    screen_name: "Đăng nhập", deadline: "2026-11-20", status: "TODO",
    returned_cases: [{ case_id: "TC-1", title: "Đăng nhập sai", comment: "Thiếu bước", returned_by: "qa@example.com" }],
  },
  {
    assignment_id: "a2", project_id: "p1", project_name: "Dự án A", screen_id: "SCR-2",
    screen_name: "Trang chủ", deadline: "2026-11-21", status: "IN_REVIEW",
  },
  {
    assignment_id: "a3", project_id: "p1", project_name: "Dự án A", screen_id: "SCR-3",
    screen_name: "Hồ sơ", deadline: "2026-11-22", status: "APPROVED",
  },
  {
    assignment_id: "a4", project_id: "p1", project_name: "Dự án A", screen_id: "SCR-4",
    screen_name: "Đăng xuất", deadline: "2026-11-23", status: "TESTED",
  },
]

function renderPage() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <MyWorkPage />
    </NextIntlClientProvider>,
  )
}

describe("MyWorkPage", () => {
  afterEach(() => {
    cleanup()
    mocks.items = []
  })

  it("mặc định chỉ hiện việc đang làm và giữ nguyên case bị trả lại", () => {
    mocks.items = items
    renderPage()

    expect(screen.getByRole("tab", { name: "Đang làm 2" })).toHaveAttribute("aria-selected", "true")
    expect(screen.getByText("Đăng nhập")).toBeInTheDocument()
    expect(screen.getByText("Trang chủ")).toBeInTheDocument()
    expect(screen.queryByText("Hồ sơ")).not.toBeInTheDocument()
    expect(screen.getByText("Đăng nhập sai")).toBeInTheDocument()
  })

  it("đặt APPROVED và TESTED ở Đã xong, với số lượng đúng", () => {
    mocks.items = items
    renderPage()
    fireEvent.click(screen.getByRole("tab", { name: "Đã xong 2" }))

    expect(screen.getByRole("tab", { name: "Đã xong 2" })).toHaveAttribute("aria-selected", "true")
    expect(screen.getByText("Hồ sơ")).toBeInTheDocument()
    expect(screen.getByText("Đăng xuất")).toBeInTheDocument()
    expect(screen.queryByText("Đăng nhập")).not.toBeInTheDocument()
  })

  it("hiện lời giải thích riêng khi mỗi tab không có việc", () => {
    renderPage()
    expect(screen.getByText("Không có việc đang làm.")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("tab", { name: "Đã xong 0" }))
    expect(screen.getByText("Chưa có việc nào đã xong.")).toBeInTheDocument()
  })
})

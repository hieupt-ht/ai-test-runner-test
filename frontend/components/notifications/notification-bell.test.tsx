import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { NotificationBell } from "@/components/notifications/notification-bell"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  read: vi.fn(),
  readAll: vi.fn(),
  data: { items: [] as Array<{ id: string; title: string; link: string; read: boolean; type: string; created_at: string }>, unread: 0 },
}))

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock("@/lib/use-notifications", () => ({
  useNotifications: () => ({ data: mocks.data, isLoading: false }),
  useMarkRead: () => ({ mutateAsync: mocks.read }),
  useMarkAllRead: () => ({ mutateAsync: mocks.readAll }),
}))

function renderBell() {
  render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <NotificationBell />
    </NextIntlClientProvider>,
  )
  fireEvent.click(screen.getByRole("button", { name: /Thông báo/ }))
}

describe("NotificationBell", () => {
  afterEach(cleanup)
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.read.mockResolvedValue(undefined)
    mocks.readAll.mockResolvedValue(undefined)
    mocks.data = { items: [], unread: 0 }
  })

  it("hiện số chưa đọc và đọc một thông báo trước khi điều hướng", async () => {
    mocks.data = {
      unread: 1,
      items: [{ id: "n1", title: "Case đã được duyệt", link: "/projects/p1/test-cases/c1", read: false, type: "case_approved", created_at: "2026-11-14T00:00:00Z" }],
    }
    renderBell()

    expect(screen.getByText("1")).toBeInTheDocument()
    fireEvent.click(screen.getByText("Case đã được duyệt"))
    await waitFor(() => expect(mocks.read).toHaveBeenCalledWith("n1"))
    expect(mocks.push).toHaveBeenCalledWith("/projects/p1/test-cases/c1")
  })

  it("ẩn số khi không có tin và hiện trạng thái rỗng", () => {
    renderBell()
    expect(screen.queryByText("0")).not.toBeInTheDocument()
    expect(screen.getByText("Chưa có thông báo")).toBeInTheDocument()
  })

  it("bấm Đọc hết để đánh dấu toàn bộ", async () => {
    mocks.data = {
      unread: 1,
      items: [{ id: "n1", title: "Tin mới", link: "/projects/p1", read: false, type: "general", created_at: "2026-11-14T00:00:00Z" }],
    }
    renderBell()
    fireEvent.click(screen.getByRole("button", { name: "Đọc hết" }))
    await waitFor(() => expect(mocks.readAll).toHaveBeenCalledOnce())
  })
})

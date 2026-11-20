import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { LeaderboardCard } from "@/components/leaderboard/leaderboard-card"
import { ProjectLeaderboards } from "@/components/leaderboard/project-leaderboards"
import type { Board, Leaderboard, Period } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  useLeaderboard: vi.fn(),
  board: undefined as unknown,
}))

vi.mock("@/lib/use-stats", () => ({
  useLeaderboard: (projectId: string, period: Period) => mocks.useLeaderboard(projectId, period),
}))
vi.mock("@/lib/use-me", () => ({
  useMe: () => ({ user: { email: "me@example.com", name: "Tôi", role: "TESTER" }, isLoading: false }),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function wrap(ui: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      {ui}
    </NextIntlClientProvider>,
  )
}

const row = (rank: number | null, email: string, name: string, count: number) => ({ rank, email, name, count })

describe("LeaderboardCard", () => {
  it("hiện huy chương cho 3 hạng đầu", () => {
    const board: Board = {
      top: [row(1, "a@x.com", "An", 9), row(2, "b@x.com", "Bình", 7), row(3, "c@x.com", "Chi", 5), row(4, "d@x.com", "Dũng", 2)],
      me: null,
    }
    wrap(<LeaderboardCard title="Viết case" board={board} meEmail="me@example.com" />)
    expect(screen.getByText("🥇")).toBeInTheDocument()
    expect(screen.getByText("🥈")).toBeInTheDocument()
    expect(screen.getByText("🥉")).toBeInTheDocument()
    // Hạng 4 hiện số, không có huy chương
    expect(screen.getByText("4")).toBeInTheDocument()
  })

  it("đánh dấu dòng của chính mình", () => {
    const board: Board = { top: [row(1, "a@x.com", "An", 9), row(2, "me@example.com", "Tôi", 7)], me: row(2, "me@example.com", "Tôi", 7) }
    wrap(<LeaderboardCard title="Viết case" board={board} meEmail="me@example.com" />)
    expect(screen.getByText("(bạn)")).toBeInTheDocument()
    // Mình đã nằm trong top thì không hiện lặp thêm dòng nữa
    expect(screen.getAllByText("Tôi")).toHaveLength(1)
  })

  it("người xem ngoài top hiện thêm dòng của mình", () => {
    const board: Board = {
      top: [row(1, "a@x.com", "An", 9)],
      me: row(8, "me@example.com", "Tôi", 1),
    }
    wrap(<LeaderboardCard title="Viết case" board={board} meEmail="me@example.com" />)
    expect(screen.getByText("…")).toBeInTheDocument()
    expect(screen.getByText("Tôi")).toBeInTheDocument()
    expect(screen.getByText("(bạn)")).toBeInTheDocument()
  })

  it("mình chưa có điểm thì hiện 'Chưa có điểm'", () => {
    const board: Board = { top: [row(1, "a@x.com", "An", 9)], me: row(null, "me@example.com", "Tôi", 0) }
    wrap(<LeaderboardCard title="Viết case" board={board} meEmail="me@example.com" />)
    expect(screen.getByText("Chưa có điểm")).toBeInTheDocument()
  })

  it("bảng chưa ai có điểm (backend vẫn trả me 0 điểm) thì hiện câu mời, không hiện dấu …", () => {
    const board: Board = { top: [], me: row(null, "me@example.com", "Tôi", 0) }
    wrap(<LeaderboardCard title="Viết case" board={board} meEmail="me@example.com" />)
    expect(screen.getByText("Chưa ai có điểm — bạn là người đầu tiên nhé!")).toBeInTheDocument()
    expect(screen.queryByText("…")).not.toBeInTheDocument()
  })

  it("bằng điểm thì cùng hạng", () => {
    const board: Board = { top: [row(1, "a@x.com", "An", 5), row(1, "b@x.com", "Bình", 5)], me: null }
    wrap(<LeaderboardCard title="Viết case" board={board} meEmail="me@example.com" />)
    expect(screen.getAllByText("🥇")).toHaveLength(2)
  })

  it("bảng trống thì hiện câu mời", () => {
    wrap(<LeaderboardCard title="Viết case" board={{ top: [], me: null }} meEmail="me@example.com" />)
    expect(screen.getByText("Chưa ai có điểm — bạn là người đầu tiên nhé!")).toBeInTheDocument()
  })
})

describe("ProjectLeaderboards", () => {
  it("đổi bộ lọc thì gọi useLeaderboard với period mới", () => {
    const data: Leaderboard = {
      period: "week",
      cases: { top: [], me: null },
      bugs: { top: [], me: null },
    }
    mocks.useLeaderboard.mockReturnValue({ data, isLoading: false })
    wrap(<ProjectLeaderboards projectId="p1" />)

    // Mặc định là Tuần này
    expect(mocks.useLeaderboard).toHaveBeenLastCalledWith("p1", "week")
    expect(screen.getByText("Viết case nhiều nhất")).toBeInTheDocument()
    expect(screen.getByText("Bắt bug nhiều nhất")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Tháng này" }))
    expect(mocks.useLeaderboard).toHaveBeenLastCalledWith("p1", "month")
    fireEvent.click(screen.getByRole("button", { name: "Tất cả" }))
    expect(mocks.useLeaderboard).toHaveBeenLastCalledWith("p1", "all")
  })
})

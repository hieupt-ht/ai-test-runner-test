import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { PetCard } from "@/components/pet/pet-card"
import type { MyPet } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({
  pet: undefined as MyPet | undefined,
}))

vi.mock("@/lib/use-stats", () => ({
  useMyPet: () => ({ data: mocks.pet, isLoading: mocks.pet === undefined }),
}))

afterEach(cleanup)

function pet(overrides: Partial<MyPet>): MyPet {
  return { level: 2, bugs: 7, bugs_to_next: 13, streak: 4, missed_days: 0, mood: "NORMAL", ...overrides }
}

function renderCard() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <PetCard />
    </NextIntlClientProvider>,
  )
}

describe("PetCard", () => {
  it("hiện chuỗi ngày và số bug còn thiếu", () => {
    mocks.pet = pet({})
    renderCard()
    expect(screen.getByText(/4 ngày/)).toBeInTheDocument()
    expect(screen.getByText("Còn 13 bug nữa lên cấp")).toBeInTheDocument()
    expect(screen.getByText("7 bug đã bắt")).toBeInTheDocument()
    expect(screen.getByText("Nhím nhỡ")).toBeInTheDocument()
  })

  it("chuỗi ngày có chữ ẩn cho trình đọc màn hình, không dùng aria-label trên thẻ p", () => {
    mocks.pet = pet({})
    const { container } = renderCard()
    expect(screen.getByText(/Chuỗi ngày liên tiếp/)).toHaveClass("sr-only")
    expect(container.querySelector("p[aria-label]")).toBeNull()
  })

  it("Vua nhím không còn thanh lên cấp", () => {
    mocks.pet = pet({ level: 4, bugs: 120, bugs_to_next: null })
    renderCard()
    expect(screen.getByText("Cấp cao nhất rồi!")).toBeInTheDocument()
    expect(screen.queryByText(/bug nữa lên cấp/)).not.toBeInTheDocument()
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument()
  })

  it("nhím đói có câu nhắc", () => {
    mocks.pet = pet({ mood: "HUNGRY", missed_days: 1 })
    renderCard()
    expect(screen.getByText("Nhím đói rồi, bắt bug cho nhím ăn nhé!")).toBeInTheDocument()
  })

  it("đang tải thì hiện khung xương, không vỡ", () => {
    mocks.pet = undefined
    const { container } = renderCard()
    expect(container.querySelector("[data-slot='skeleton']")).toBeInTheDocument()
    expect(screen.queryByRole("img")).not.toBeInTheDocument()
  })
})

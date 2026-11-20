import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it } from "vitest"

import { Hedgehog } from "@/components/pet/hedgehog"
import messages from "@/messages/vi.json"

afterEach(cleanup)

function renderWithIntl(ui: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      {ui}
    </NextIntlClientProvider>,
  )
}

describe("Hedgehog", () => {
  it("mỗi biểu cảm có nhãn riêng", () => {
    renderWithIntl(
      <>
        <Hedgehog level={1} mood="HAPPY" />
        <Hedgehog level={1} mood="NORMAL" />
        <Hedgehog level={1} mood="HUNGRY" />
        <Hedgehog level={1} mood="CRY" />
      </>,
    )
    expect(screen.getByRole("img", { name: "Nhím Nhím con, Cười" })).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "Nhím Nhím con, Bình thường" })).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "Nhím Nhím con, Đói" })).toBeInTheDocument()
    expect(screen.getByRole("img", { name: "Nhím Nhím con, Khóc" })).toBeInTheDocument()
  })

  it("chỉ Vua nhím đội vương miện", () => {
    const { rerender } = renderWithIntl(<Hedgehog level={3} mood="NORMAL" />)
    expect(screen.queryByTestId("crown")).not.toBeInTheDocument()
    rerender(
      <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
        <Hedgehog level={4} mood="NORMAL" />
      </NextIntlClientProvider>,
    )
    expect(screen.getByTestId("crown")).toBeInTheDocument()
  })

  it("nhím lớn dần theo cấp", () => {
    renderWithIntl(
      <>
        <Hedgehog level={1} mood="NORMAL" />
        <Hedgehog level={4} mood="NORMAL" />
      </>,
    )
    const [small, big] = screen.getAllByRole("img")
    expect(Number(small.getAttribute("width"))).toBeLessThan(Number(big.getAttribute("width")))
  })

  it("hai con nhím trên một trang không trùng id gradient", () => {
    const { container } = renderWithIntl(
      <>
        <Hedgehog level={2} mood="HAPPY" />
        <Hedgehog level={2} mood="HAPPY" />
      </>,
    )
    const ids = Array.from(container.querySelectorAll("[id]")).map((node) => node.id)
    expect(ids.length).toBeGreaterThan(0)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it } from "vitest"

import { CaseReadOnly } from "@/components/test-cases/case-read-only"
import type { TestCase, TestStep } from "@/lib/api/types"
import messages from "@/messages/vi.json"

afterEach(cleanup)

function renderCase(steps: TestStep[]) {
  const testCase = {
    id: "TC-000001",
    screen_id: "SC-0001",
    title: "Đăng nhập",
    precondition: "",
    test_data: "",
    steps,
    expected_result: "Vào được trang chủ",
    severity: "HIGH",
    priority: "P1",
    status: "APPROVED",
  } as TestCase
  render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <CaseReadOnly testCase={testCase} />
    </NextIntlClientProvider>,
  )
}

describe("CaseReadOnly — bước tự động", () => {
  it("hiện tóm tắt một dòng cho bước có phần tự động", () => {
    renderCase([
      { action: "Nhập email", expected: "", auto: { type: "fill", value: "qa@x.com", target: { by: "label", value: "Email" } } },
      { action: "Bấm nút", expected: "", auto: { type: "click", value: "", target: { by: "text", value: "Gửi" } } },
      { action: "Mở", expected: "", auto: { type: "goto", value: "/login" } },
    ])

    expect(screen.getByText('Nhập "qa@x.com" vào ô "Email"')).toBeInTheDocument()
    expect(screen.getByText('Bấm chữ "Gửi"')).toBeInTheDocument()
    expect(screen.getByText("Mở trang /login")).toBeInTheDocument()
  })

  it("bước không có phần tự động thì không hiện dòng tóm tắt", () => {
    renderCase([{ action: "Mở trang", expected: "" }])

    expect(screen.queryByText(/Tự động/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Mở trang \//)).not.toBeInTheDocument()
  })
})

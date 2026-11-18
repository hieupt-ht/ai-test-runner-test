import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ReviewActions } from "@/components/test-cases/review-actions"
import type { TestCaseDetail } from "@/lib/api/types"
import messages from "@/messages/vi.json"

vi.mock("@/lib/use-test-cases", () => ({
  useTransitionTestCase: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

const inReview = {
  id: "TC-1",
  version: 2,
  status: "IN_REVIEW",
  can_edit: false,
  can_review: true,
} as TestCaseDetail

function renderActions(reviewDisabled: boolean) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ReviewActions projectId="P1" testCase={inReview} reviewDisabled={reviewDisabled} />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  )
}

describe("ReviewActions", () => {
  afterEach(cleanup)

  it("làm mờ nút Duyệt và Trả lại, kèm gợi ý, khi dự án tắt bước duyệt", () => {
    renderActions(true)
    for (const name of ["Duyệt", "Trả lại"]) {
      const button = screen.getByRole("button", { name })
      expect(button).toBeDisabled()
      expect(button).toHaveAttribute("title", "Dự án đang tắt bước duyệt")
    }
  })

  it("bật bình thường khi dự án có bước duyệt", () => {
    renderActions(false)
    expect(screen.getByRole("button", { name: "Duyệt" })).toBeEnabled()
    expect(screen.getByRole("button", { name: "Trả lại" })).toBeEnabled()
  })
})

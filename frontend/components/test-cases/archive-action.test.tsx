import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ArchiveAction } from "@/components/test-cases/archive-action"
import type { TestCaseDetail } from "@/lib/api/types"
import messages from "@/messages/vi.json"

vi.mock("@/lib/use-test-cases", () => ({
  useArchiveTestCase: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function renderAction(status: TestCaseDetail["status"], canArchive: boolean) {
  const testCase = {
    id: "TC-1",
    version: 3,
    status,
    can_archive: canArchive,
  } as TestCaseDetail
  return render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <ArchiveAction projectId="P1" testCase={testCase} />
    </NextIntlClientProvider>,
  )
}

describe("ArchiveAction", () => {
  afterEach(cleanup)

  it("chỉ hiện nút lưu trữ cho case đã duyệt hoặc kiểm thử và đúng quyền", () => {
    const { rerender } = renderAction("APPROVED", true)
    expect(screen.getByRole("button", { name: "Lưu trữ" })).toBeInTheDocument()

    rerender(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ArchiveAction projectId="P1" testCase={{ id: "TC-1", version: 3, status: "APPROVED", can_archive: false } as TestCaseDetail} />
      </NextIntlClientProvider>,
    )
    expect(screen.queryByRole("button", { name: "Lưu trữ" })).not.toBeInTheDocument()
  })

  it("hiện nút khôi phục cho case archived khi có quyền", () => {
    renderAction("ARCHIVED", true)
    expect(screen.getByRole("button", { name: "Khôi phục" })).toBeInTheDocument()
  })
})

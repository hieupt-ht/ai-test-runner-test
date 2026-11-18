import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it } from "vitest"

import { HistoryPanel } from "@/components/test-cases/history-panel"
import type { AuditEntry } from "@/lib/api/types"
import messages from "@/messages/vi.json"

function entry(at: string, action: string, diff: Record<string, unknown>): AuditEntry {
  return { at, actor: "lan@x.com", action, entity: "test_case", entity_id: "TC-1", diff } as AuditEntry
}

describe("HistoryPanel", () => {
  afterEach(cleanup)

  it("hiện phiên bản, giờ Việt Nam, người sửa và các trường đã đổi", () => {
    render(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <HistoryPanel
          history={[
            entry("2026-11-16T05:00:00Z", "CREATE", {}),
            entry("2026-11-16T06:00:00Z", "SUBMIT", { status: ["DRAFT", "APPROVED"] }),
            entry("2026-11-16T07:05:00Z", "UPDATE", { steps: [[], []], platform: ["WEB", "ANDROID"] }),
          ]}
        />
      </NextIntlClientProvider>,
    )

    expect(screen.getByText(/v3 · 16\/11\/2026 14:05 · lan@x.com/)).toBeInTheDocument()
    expect(screen.getByText(/Các bước, Nền tảng/)).toBeInTheDocument()
  })

  it("hiện tên thao tác tự duyệt khi tắt bước duyệt", () => {
    render(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <HistoryPanel history={[entry("2026-11-16T07:05:00Z", "AUTO_APPROVE", {})]} />
      </NextIntlClientProvider>,
    )
    expect(screen.getByText("Tự duyệt (tắt bước duyệt)")).toBeInTheDocument()
  })
})

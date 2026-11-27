import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ModuleFormDialog } from "@/components/modules/module-form-dialog"
import messages from "@/messages/vi.json"

const mutateAsync = vi.fn()
vi.mock("@/lib/use-modules", () => ({
  useSaveModule: () => ({ mutateAsync, isPending: false }),
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

afterEach(() => {
  cleanup()
  mutateAsync.mockReset()
})

describe("ModuleFormDialog", () => {
  it("gọi onSaved với module vừa tạo", async () => {
    const created = { id: "MD-0009", name: "Thanh toán", description: "" }
    mutateAsync.mockResolvedValue(created)
    const onSaved = vi.fn()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <NextIntlClientProvider locale="vi" messages={messages}>
          <ModuleFormDialog
            projectId="P1"
            trigger={<button type="button" />}
            triggerLabel="Mở"
            onSaved={onSaved}
          />
        </NextIntlClientProvider>
      </QueryClientProvider>,
    )
    fireEvent.click(screen.getByText("Mở"))
    fireEvent.change(screen.getByLabelText("Tên module"), { target: { value: "Thanh toán" } })
    fireEvent.click(screen.getByRole("button", { name: "Lưu" }))

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(created))
  })
})

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { toast } from "sonner"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import AdminProjectsPage from "@/app/(app)/admin/projects/page"
import { ApiError } from "@/lib/api/client"
import type { Project } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ update: vi.fn() }))

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }))
vi.mock("@/lib/use-me", () => ({
  useMe: () => ({ user: { email: "a@x.com", name: "A", role: "ADMIN", active: true } }),
}))
vi.mock("@/components/projects/create-project-dialog", () => ({
  CreateProjectDialog: () => null,
}))
vi.mock("@/lib/use-projects", () => ({
  useProjects: () => ({ data: [project], isLoading: false }),
  useUpdateProject: (id: string) => ({
    mutateAsync: (body: unknown) => mocks.update(id, body),
    isPending: false,
  }),
}))

const project: Project = {
  id: "PRJ-0001",
  name: "Dự án A",
  repo_full_name: "org/repo",
  branch: "main",
  staging_url: "",
  spreadsheet_id: "sheet-1",
  archived: false,
  created_at: "2026-11-01T00:00:00Z",
  android_app_id: "",
  ios_bundle_id: "",
  require_review: false,
  storage: "cloudinary",
}

function renderPage() {
  render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <AdminProjectsPage />
    </NextIntlClientProvider>,
  )
  return screen.getByRole("combobox", { name: "Nơi lưu ảnh/video của Dự án A" }) as HTMLSelectElement
}

describe("Admin: nơi lưu ảnh/video của dự án", () => {
  beforeEach(() => {
    mocks.update.mockReset()
    vi.mocked(toast.error).mockClear()
  })
  afterEach(cleanup)

  it("hiện nơi lưu hiện tại của dự án", () => {
    expect(renderPage().value).toBe("cloudinary")
  })

  it("đổi sang Google Drive thì gửi PATCH storage drive", async () => {
    mocks.update.mockResolvedValue({ ...project, storage: "drive" })
    const select = renderPage()

    fireEvent.change(select, { target: { value: "drive" } })

    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith("PRJ-0001", { storage: "drive" }))
  })

  it("backend từ chối (422) thì báo lỗi của backend và ô chọn quay về giá trị cũ", async () => {
    mocks.update.mockRejectedValue(new ApiError(422, "Chưa cấu hình Google Drive"))
    const select = renderPage()

    fireEvent.change(select, { target: { value: "drive" } })

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Chưa cấu hình Google Drive"))
    expect(select.value).toBe("cloudinary")
  })
})

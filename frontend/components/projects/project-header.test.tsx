import { cleanup, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ProjectHeader } from "@/components/projects/project-header"
import messages from "@/messages/vi.json"

vi.mock("@/lib/use-project-id", () => ({ useProjectId: () => "p1" }))
vi.mock("next/navigation", () => ({ usePathname: () => "/projects/p1" }))
vi.mock("@/lib/use-projects", () => ({
  useProject: () => ({
    data: {
      id: "p1",
      name: "Dự án A",
      archived: false,
      repo_full_name: "org/repo",
      branch: "main",
      spreadsheet_id: "sheet-1",
      permissions: ["VIEW_PROJECT"],
    },
    isLoading: false,
    isError: false,
  }),
}))

describe("ProjectHeader", () => {
  afterEach(cleanup)

  it("giữ thông tin repo và Sheet nhưng không còn thanh tab ngang", () => {
    const { container } = render(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <ProjectHeader />
      </NextIntlClientProvider>,
    )

    expect(screen.getByText("Dự án A")).toBeInTheDocument()
    expect(screen.getByText("org/repo@main")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Mở Google Sheet" })).toHaveAttribute(
      "href",
      "https://docs.google.com/spreadsheets/d/sheet-1",
    )
    expect(container.querySelector("nav")).not.toBeInTheDocument()
  })
})

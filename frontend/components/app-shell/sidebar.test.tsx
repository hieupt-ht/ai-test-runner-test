import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { Sidebar } from "@/components/app-shell/sidebar"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ pathname: "/", projects: [] as { id: string; name: string; archived: boolean }[] }))

vi.mock("next/navigation", () => ({ usePathname: () => mocks.pathname }))
vi.mock("@/lib/use-projects", () => ({
  useProjects: () => ({ data: mocks.projects }),
  useProject: () => ({ data: { permissions: ["VIEW_PROJECT"] } }),
}))

function renderSidebar() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <Sidebar role="TESTER" />
    </NextIntlClientProvider>,
  )
}

describe("Sidebar", () => {
  afterEach(() => {
    cleanup()
    mocks.pathname = "/"
    mocks.projects = []
  })

  it("ẩn các trang con trước khi project được mở", () => {
    mocks.projects = [{ id: "p1", name: "Dự án A", archived: false }]
    renderSidebar()

    expect(screen.queryByRole("link", { name: "Kết quả" })).not.toBeInTheDocument()
  })

  it("mở các trang con khi bấm nút project", () => {
    mocks.projects = [{ id: "p1", name: "Dự án A", archived: false }]
    renderSidebar()

    fireEvent.click(screen.getAllByRole("button", { name: "Dự án A" })[0])
    expect(screen.getAllByRole("link", { name: "Kết quả" })[0]).toHaveAttribute(
      "href",
      "/projects/p1/results",
    )
  })

  it("tự mở project hiện tại và đánh dấu trang đang xem", () => {
    mocks.projects = [{ id: "p1", name: "Dự án A", archived: false }]
    mocks.pathname = "/projects/p1/results"
    renderSidebar()

    expect(screen.getAllByRole("link", { name: "Kết quả" })[0]).toHaveAttribute("aria-current", "page")
  })

  it("chỉ có một mục Tổng quan trong project", () => {
    mocks.projects = [{ id: "p1", name: "Dự án A", archived: false }]
    mocks.pathname = "/projects/p1/overview"
    renderSidebar()

    // Sidebar có hai bản (máy tính và điện thoại) nên mỗi mục xuất hiện 2 lần
    const links = screen.getAllByRole("link", { name: "Tổng quan" })
    const projectLinks = links.filter((a) => a.getAttribute("href")?.startsWith("/projects/p1"))
    expect(projectLinks.map((a) => a.getAttribute("href"))).toEqual([
      "/projects/p1/overview",
      "/projects/p1/overview",
    ])
  })

  it("project đang xem vẫn thu lại được khi bấm nút, bấm nữa thì mở lại", () => {
    mocks.projects = [{ id: "p1", name: "Dự án A", archived: false }]
    mocks.pathname = "/projects/p1/results"
    renderSidebar()

    const button = screen.getAllByRole("button", { name: "Dự án A" })[0]
    expect(button).toHaveAttribute("aria-expanded", "true")

    fireEvent.click(button)
    expect(screen.getAllByRole("button", { name: "Dự án A" })[0]).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByRole("link", { name: "Kết quả" })).not.toBeInTheDocument()

    fireEvent.click(screen.getAllByRole("button", { name: "Dự án A" })[0])
    expect(screen.getAllByRole("link", { name: "Kết quả" })[0]).toBeInTheDocument()
  })
})

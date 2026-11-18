import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ResultDetail } from "@/components/results/result-detail"
import { makeResult } from "@/components/results/result-fixture"
import type { Media, ResultItem } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const shot = (name: string): Media => ({
  kind: "image",
  url: `https://res.cloudinary.com/m/image/upload/${name}.png`,
  public_id: name,
  note: "",
})

function renderDetail(result: ResultItem | null, onClose = vi.fn()) {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <ResultDetail result={result} onClose={onClose} />
    </NextIntlClientProvider>,
  )
}

afterEach(cleanup)

describe("ResultDetail", () => {
  it("hiện tiêu đề, phiên bản, môi trường, dev và người chạy", () => {
    renderDetail(makeResult())
    expect(screen.getByText(/TC-000005/)).toBeInTheDocument()
    expect(screen.getByText("FAIL · v2 · Pixel 7 / Android 14")).toBeInTheDocument()
    expect(screen.getByText("Dev phụ trách: @nguyenvana")).toBeInTheDocument()
    expect(screen.getByText("Chạy bởi codex-windows")).toBeInTheDocument()
  })

  it("không hiện dòng dev khi chưa có dev phụ trách", () => {
    renderDetail(makeResult({ dev_owner: "" }))
    expect(screen.queryByText(/Dev phụ trách/)).not.toBeInTheDocument()
  })

  it("có trình phát video khi kết quả có video", () => {
    const video: Media = { kind: "video", url: "https://res.cloudinary.com/m/video/upload/v.mp4", public_id: "v", note: "" }
    const { baseElement } = renderDetail(makeResult({ evidence: { pruned: false, video } }))
    const player = baseElement.querySelector("video")
    expect(player).toHaveAttribute("src", video.url)
    expect(player).toHaveAttribute("controls")
  })

  it("video lưu ở Drive phát bằng iframe, ảnh Drive dùng thumbnail", () => {
    const video: Media = { kind: "video", url: "https://drive.google.com/file/d/V1/view", public_id: "V1", note: "" }
    const image: Media = { kind: "image", url: "https://drive.google.com/file/d/I1/view", public_id: "I1", note: "" }
    const { baseElement } = renderDetail(
      makeResult({ evidence: { pruned: false, video, screenshots: [image] } }),
    )
    expect(baseElement.querySelector("iframe")).toHaveAttribute(
      "src",
      "https://drive.google.com/file/d/V1/preview",
    )
    expect(baseElement.querySelector("video")).toBeNull()
    expect(baseElement.querySelector("img")).toHaveAttribute(
      "src",
      "https://drive.google.com/thumbnail?id=I1&sz=w1600",
    )
  })

  it("bảng bước: ảnh mở lightbox và bước không chạy hiện 'Không chạy'", () => {
    renderDetail(
      makeResult({
        step_results: [
          { step_no: 1, status: "PASS", actual: "ok" },
          { step_no: 2, status: "FAIL", actual: "Lỗi", screenshot: shot("err") },
          { step_no: 3, status: "SKIPPED", actual: "" },
        ],
      }),
    )
    expect(screen.getByText("Không chạy")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Xem ảnh bước 2" }))
    expect(screen.getByRole("img", { name: /ảnh/i })).toHaveAttribute(
      "src",
      "https://res.cloudinary.com/m/image/upload/err.png",
    )
  })

  it("bằng chứng đã dọn thì báo rõ", () => {
    renderDetail(makeResult({ evidence: { pruned: true } }))
    expect(screen.getByText("Bằng chứng đã được dọn")).toBeInTheDocument()
  })

  it("bằng chứng kiểu cũ là một link an toàn", () => {
    renderDetail(makeResult({ evidence: { pruned: false, legacy_url: "https://example.com/a.png" } }))
    expect(screen.getByRole("link", { name: "Mở bằng chứng" })).toHaveAttribute(
      "href",
      "https://example.com/a.png",
    )
  })

  it("không tạo link khi bằng chứng kiểu cũ không phải http(s)", () => {
    renderDetail(makeResult({ evidence: { pruned: false, legacy_url: "javascript:alert(1)" } }))
    expect(screen.queryByRole("link", { name: "Mở bằng chứng" })).not.toBeInTheDocument()
  })

  it("có link sang issue và không hiện gì khi chưa chọn kết quả", () => {
    const { rerender } = renderDetail(makeResult())
    expect(screen.getByRole("link", { name: "Mở issue trên GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/org/web/issues?q=label%3Atc%3ATC-000005",
    )
    rerender(
      <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
        <ResultDetail result={null} onClose={vi.fn()} />
      </NextIntlClientProvider>,
    )
    expect(screen.queryByText(/TC-000005/)).not.toBeInTheDocument()
  })
})

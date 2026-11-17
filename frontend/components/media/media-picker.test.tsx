import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { MediaPicker } from "@/components/media/media-picker"
import type { Media } from "@/lib/api/types"
import messages from "@/messages/vi.json"

vi.mock("@/lib/media/upload", async (original) => ({
  ...(await original<typeof import("@/lib/media/upload")>()),
  uploadMedia: vi.fn(),
}))

function media(id: string, kind: "image" | "video" = "image"): Media {
  return {
    kind,
    url: `https://res.cloudinary.com/demo/${kind}/upload/${id}`,
    public_id: id,
    note: "",
  }
}

function renderPicker(value: Media[], onChange = vi.fn(), max = 5) {
  render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <MediaPicker value={value} onChange={onChange} max={max} projectId="PRJ-0001" />
    </NextIntlClientProvider>,
  )
  return onChange
}

describe("MediaPicker", () => {
  afterEach(cleanup)

  it("còn chỗ thì có nút Thêm ảnh/video", () => {
    renderPicker([media("a")])
    expect(screen.getByRole("button", { name: "Thêm ảnh/video" })).toBeInTheDocument()
  })

  it("đủ 5 mục thì không còn nút Thêm ảnh/video", () => {
    renderPicker(["a", "b", "c", "d", "e"].map((id) => media(id)))
    expect(screen.queryByRole("button", { name: "Thêm ảnh/video" })).not.toBeInTheDocument()
  })

  it("bấm xoá gọi onChange với danh sách thiếu mục đó", () => {
    const onChange = renderPicker([media("a"), media("b")])
    fireEvent.click(screen.getAllByRole("button", { name: "Xoá ảnh/video" })[0])
    expect(onChange).toHaveBeenCalledWith([media("b")])
  })

  it("sửa ghi chú cập nhật đúng mục", () => {
    const onChange = renderPicker([media("a"), media("b")])
    fireEvent.change(screen.getAllByPlaceholderText("Ghi chú ngắn (không bắt buộc)")[1], {
      target: { value: "nút Đăng nhập" },
    })
    expect(onChange).toHaveBeenCalledWith([media("a"), { ...media("b"), note: "nút Đăng nhập" }])
  })

  it("video có thẻ video có nút điều khiển, ảnh bấm mở xem lớn", () => {
    const { container } = render(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <MediaPicker
          value={[media("a"), media("v", "video")]}
          onChange={vi.fn()}
          max={5}
          projectId="PRJ-0001"
        />
      </NextIntlClientProvider>,
    )
    expect(container.querySelector("video")).toHaveAttribute("controls")
    fireEvent.click(screen.getByRole("button", { name: "Xem ảnh lớn" }))
    expect(within(screen.getByRole("dialog")).getByRole("img")).toBeInTheDocument()
  })
})

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { MediaPicker } from "@/components/media/media-picker"
import type { Media } from "@/lib/api/types"
import { uploadMedia } from "@/lib/media/upload"
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

  it("dán ảnh (Ctrl+V) trong ô thì tải ảnh đó lên", async () => {
    vi.mocked(uploadMedia).mockResolvedValue(media("pasted"))
    const onChange = renderPicker([])
    const file = new File(["x"], "image.png", { type: "image/png" })
    fireEvent.paste(screen.getByRole("group", { name: "Ảnh/video hướng dẫn" }), {
      clipboardData: { files: [file], items: [] },
    })
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([media("pasted")]))
    expect(uploadMedia).toHaveBeenCalledWith(file, expect.objectContaining({ projectId: "PRJ-0001" }))
  })

  it("pasteScope=page: dán ảnh ở bất kỳ đâu trên trang cũng tải lên", async () => {
    vi.mocked(uploadMedia).mockResolvedValue(media("anywhere"))
    const onChange = vi.fn()
    render(
      <NextIntlClientProvider locale="vi" messages={messages}>
        <input aria-label="ô khác" />
        <MediaPicker value={[]} onChange={onChange} projectId="PRJ-0001" pasteScope="page" />
      </NextIntlClientProvider>,
    )
    const file = new File(["x"], "image.png", { type: "image/png" })
    fireEvent.paste(screen.getByLabelText("ô khác"), {
      clipboardData: { files: [file], items: [] },
    })
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([media("anywhere")]))
  })

  it("dán chữ thì bỏ qua, không tải gì lên", () => {
    vi.mocked(uploadMedia).mockClear()
    renderPicker([])
    fireEvent.paste(screen.getByRole("group", { name: "Ảnh/video hướng dẫn" }), {
      clipboardData: { files: [], items: [] },
    })
    expect(uploadMedia).not.toHaveBeenCalled()
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

  describe("kho Google Drive", () => {
    const driveMedia = (kind: "image" | "video"): Media => ({
      kind,
      url: "https://drive.google.com/file/d/F1/view",
      public_id: "F1",
      note: "",
    })

    it("ảnh Drive hiện bằng thumbnail, video Drive hiện bằng iframe", () => {
      const { container } = render(
        <NextIntlClientProvider locale="vi" messages={messages}>
          <MediaPicker
            value={[driveMedia("image"), { ...driveMedia("video"), public_id: "F2" }]}
            onChange={vi.fn()}
            projectId="PRJ-0001"
            storage="drive"
          />
        </NextIntlClientProvider>,
      )
      expect(container.querySelector("img")).toHaveAttribute(
        "src",
        "https://drive.google.com/thumbnail?id=F1&sz=w1600",
      )
      expect(container.querySelector("iframe")).toHaveAttribute(
        "src",
        "https://drive.google.com/file/d/F2/preview",
      )
      expect(container.querySelector("video")).toBeNull()
    })

    it("truyền mục đích tải lên (bằng chứng) xuống uploadMedia", async () => {
      vi.mocked(uploadMedia).mockResolvedValue(driveMedia("image"))
      const { container } = render(
        <NextIntlClientProvider locale="vi" messages={messages}>
          <MediaPicker value={[]} onChange={vi.fn()} projectId="PRJ-0001" purpose="evidence" />
        </NextIntlClientProvider>,
      )
      const file = new File(["x"], "image.png", { type: "image/png" })
      fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, {
        target: { files: [file] },
      })
      await waitFor(() =>
        expect(uploadMedia).toHaveBeenCalledWith(
          file,
          expect.objectContaining({ purpose: "evidence" }),
        ),
      )
    })

    it("tải lên theo nơi lưu của dự án", async () => {
      vi.mocked(uploadMedia).mockResolvedValue(driveMedia("image"))
      const onChange = vi.fn()
      const { container } = render(
        <NextIntlClientProvider locale="vi" messages={messages}>
          <MediaPicker value={[]} onChange={onChange} projectId="PRJ-0001" storage="drive" />
        </NextIntlClientProvider>,
      )
      const file = new File(["x"], "image.png", { type: "image/png" })
      fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, {
        target: { files: [file] },
      })
      await waitFor(() => expect(onChange).toHaveBeenCalled())
      expect(uploadMedia).toHaveBeenCalledWith(
        file,
        expect.objectContaining({ projectId: "PRJ-0001", storage: "drive" }),
      )
    })
  })
})

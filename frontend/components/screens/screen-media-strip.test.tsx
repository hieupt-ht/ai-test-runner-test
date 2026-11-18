import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it } from "vitest"

import { ScreenMediaStrip } from "@/components/screens/screen-media-strip"
import type { Media } from "@/lib/api/types"
import messages from "@/messages/vi.json"

const image: Media = {
  kind: "image",
  public_id: "guide/a",
  url: "https://res.cloudinary.com/demo/image/upload/a.png",
  note: "Màn đăng nhập",
}
const driveVideo: Media = {
  kind: "video",
  public_id: "abc123",
  url: "https://drive.google.com/file/d/abc123/view",
  note: "",
}

function show(media: Media[]) {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages}>
      <ScreenMediaStrip media={media} />
    </NextIntlClientProvider>,
  )
}

describe("ScreenMediaStrip", () => {
  afterEach(cleanup)

  it("rỗng thì không hiện gì", () => {
    const { container } = show([])
    expect(container).toBeEmptyDOMElement()
  })

  it("bấm ảnh thì mở ảnh lớn", () => {
    show([image])
    fireEvent.click(screen.getByRole("button", { name: /Màn đăng nhập/ }))
    expect(within(screen.getByRole("dialog")).getByRole("img")).toBeInTheDocument()
  })

  it("video Drive hiện bằng iframe", () => {
    const { container } = show([driveVideo])
    expect(container.querySelector("iframe")).not.toBeNull()
    expect(container.querySelector("img")).toBeNull()
  })
})

import { describe, expect, it } from "vitest"

import type { Media } from "@/lib/api/types"
import { displayUrl, embedUrl, isDrive } from "@/lib/media/display"

const drive = (kind: Media["kind"]): Media => ({
  kind,
  url: "https://drive.google.com/file/d/ABC_1-x/view",
  public_id: "ABC_1-x",
  note: "",
})
const cloud = (kind: Media["kind"]): Media => ({
  kind,
  url: "https://res.cloudinary.com/demo/image/upload/a.png",
  public_id: "a",
  note: "",
})

describe("isDrive", () => {
  it("nhận ra link Drive", () => {
    expect(isDrive(drive("image"))).toBe(true)
    expect(isDrive(cloud("image"))).toBe(false)
  })
})

describe("displayUrl", () => {
  it("ảnh Drive dùng thumbnail", () => {
    expect(displayUrl(drive("image"))).toBe(
      "https://drive.google.com/thumbnail?id=ABC_1-x&sz=w1600",
    )
  })
  it("video Drive và file Cloudinary giữ link gốc", () => {
    expect(displayUrl(drive("video"))).toBe(drive("video").url)
    expect(displayUrl(cloud("image"))).toBe(cloud("image").url)
  })
})

describe("embedUrl", () => {
  it("chỉ video Drive có link nhúng", () => {
    expect(embedUrl(drive("video"))).toBe("https://drive.google.com/file/d/ABC_1-x/preview")
    expect(embedUrl(drive("image"))).toBeNull()
    expect(embedUrl(cloud("video"))).toBeNull()
  })
})

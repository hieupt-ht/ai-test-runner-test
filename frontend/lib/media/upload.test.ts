import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { checkFile, kindOf, uploadMedia, videoDuration } from "@/lib/media/upload"

const post = vi.fn()
vi.mock("@/lib/api/client", async (original) => ({
  ...(await original<typeof import("@/lib/api/client")>()),
  api: { POST: (...args: unknown[]) => post(...args) },
}))

const MB = 1024 * 1024

function fileOf(name: string, type: string, size = 1000): File {
  const file = new File(["x"], name, { type })
  Object.defineProperty(file, "size", { value: size })
  return file
}

describe("checkFile", () => {
  it("ảnh quá 10MB thì báo tooLarge, đúng 10MB thì được", () => {
    expect(checkFile(fileOf("a.png", "image/png", 11 * MB), "image")).toBe("tooLarge")
    expect(checkFile(fileOf("a.png", "image/png", 10 * MB), "image")).toBeNull()
  })

  it("video quá 100MB thì báo tooLarge", () => {
    expect(checkFile(fileOf("a.mp4", "video/mp4", 101 * MB), "video")).toBe("tooLarge")
    expect(checkFile(fileOf("a.mp4", "video/mp4", 100 * MB), "video")).toBeNull()
  })

  it("file lạ (.exe) thì báo badType", () => {
    expect(checkFile(fileOf("a.exe", "application/octet-stream"), "image")).toBe("badType")
    expect(checkFile(fileOf("a.png", "image/png"), "video")).toBe("badType")
  })

  it("nhận các định dạng Cloudinary cho phép", () => {
    expect(checkFile(fileOf("a.webp", "image/webp"), "image")).toBeNull()
    expect(checkFile(fileOf("a.mov", "video/quicktime"), "video")).toBeNull()
    expect(checkFile(fileOf("a.webm", "video/webm"), "video")).toBeNull()
  })
})

describe("kindOf", () => {
  it("đoán loại theo kiểu file", () => {
    expect(kindOf(fileOf("a.png", "image/png"))).toBe("image")
    expect(kindOf(fileOf("a.mp4", "video/mp4"))).toBe("video")
    expect(kindOf(fileOf("a.exe", "application/octet-stream"))).toBeNull()
  })
})

describe("videoDuration", () => {
  const realCreate = document.createElement.bind(document)

  function fakeVideo(duration: number | "error") {
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      if (tag !== "video") return realCreate(tag)
      const video = { preload: "", onloadedmetadata: null, onerror: null, duration } as never as {
        onloadedmetadata: (() => void) | null
        onerror: (() => void) | null
        duration: number | "error"
        src: string
      }
      Object.defineProperty(video, "src", {
        set() {
          queueMicrotask(() => (duration === "error" ? video.onerror?.() : video.onloadedmetadata?.()))
        },
      })
      return video as never
    })
    URL.createObjectURL = vi.fn(() => "blob:x")
    URL.revokeObjectURL = vi.fn()
  }

  afterEach(() => vi.restoreAllMocks())

  it("trả số giây của video", async () => {
    fakeVideo(42)
    await expect(videoDuration(fileOf("a.mp4", "video/mp4"))).resolves.toBe(42)
  })

  it("từ chối video dài hơn 3 phút với khoá tooLong", async () => {
    fakeVideo(181)
    await expect(videoDuration(fileOf("a.mp4", "video/mp4"))).rejects.toMatchObject({
      key: "tooLong",
    })
  })

  it("không đọc được video thì báo badType", async () => {
    fakeVideo("error")
    await expect(videoDuration(fileOf("a.mp4", "video/mp4"))).rejects.toMatchObject({
      key: "badType",
    })
  })
})

const SIGNED = {
  cloud_name: "demo",
  api_key: "key123",
  timestamp: 1700000000,
  signature: "sig",
  folder: "ai-test-runner/PRJ-0001/guide",
  public_id: "abc",
  allowed_formats: "jpg,jpeg,png,webp,gif",
  resource_type: "image",
  max_bytes: 10 * MB,
  upload_url: "https://api.cloudinary.com/v1_1/demo/image/upload",
}

class FakeXhr {
  static instance: FakeXhr
  upload: { onprogress: ((event: unknown) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  status = 200
  responseText = JSON.stringify({
    secure_url: "https://res.cloudinary.com/demo/image/upload/v1/ai-test-runner/PRJ-0001/guide/abc.png",
    public_id: "ai-test-runner/PRJ-0001/guide/abc",
  })
  open = vi.fn()
  abort = vi.fn(() => this.onabort?.())
  sent: FormData | null = null
  constructor() {
    FakeXhr.instance = this
  }
  send(body: FormData) {
    this.sent = body
    this.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 })
    this.onload?.()
  }
}

describe("uploadMedia", () => {
  beforeEach(() => {
    post.mockReset()
    post.mockResolvedValue({ data: SIGNED, response: { status: 200, ok: true } })
    vi.stubGlobal("XMLHttpRequest", FakeXhr)
  })
  afterEach(() => vi.unstubAllGlobals())

  it("xin chữ ký, tải lên, báo tiến độ và trả đúng secure_url", async () => {
    const progress: number[] = []
    const media = await uploadMedia(fileOf("a.png", "image/png"), {
      projectId: "PRJ-0001",
      onProgress: (percent) => progress.push(percent),
    })

    expect(post).toHaveBeenCalledWith("/api/projects/{project_id}/media/sign", {
      params: { path: { project_id: "PRJ-0001" } },
      body: { kind: "image", purpose: "guide" },
    })
    expect(progress).toContain(50)
    expect(media).toEqual({
      kind: "image",
      url: "https://res.cloudinary.com/demo/image/upload/v1/ai-test-runner/PRJ-0001/guide/abc.png",
      public_id: "ai-test-runner/PRJ-0001/guide/abc",
      note: "",
    })
    expect(FakeXhr.instance.open).toHaveBeenCalledWith("POST", SIGNED.upload_url)
    const form = FakeXhr.instance.sent as FormData
    expect(form.get("signature")).toBe("sig")
    expect(form.get("api_key")).toBe("key123")
    expect(form.get("folder")).toBe(SIGNED.folder)
    expect(form.get("api_secret")).toBeNull()
  })

  it("file sai thì không gọi API ký", async () => {
    await expect(
      uploadMedia(fileOf("a.exe", "application/octet-stream"), { projectId: "PRJ-0001" }),
    ).rejects.toMatchObject({ key: "badType" })
    expect(post).not.toHaveBeenCalled()
  })

  it("Cloudinary trả lỗi thì ném lỗi uploadFailed", async () => {
    class Failing extends FakeXhr {
      status = 400
    }
    vi.stubGlobal("XMLHttpRequest", Failing)
    await expect(
      uploadMedia(fileOf("a.png", "image/png"), { projectId: "PRJ-0001" }),
    ).rejects.toMatchObject({ key: "uploadFailed" })
  })
})

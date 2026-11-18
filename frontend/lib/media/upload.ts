import { api } from "@/lib/api/client"
import { unwrap } from "@/lib/api/request"
import type { Media, MediaKind } from "@/lib/api/types"

// Giới hạn khớp với backend (app/core/media/cloudinary.py)
export const MAX_BYTES: Record<MediaKind, number> = {
  image: 10 * 1024 * 1024,
  video: 100 * 1024 * 1024,
}
export const MAX_VIDEO_SECONDS = 180

const ALLOWED_TYPES: Record<MediaKind, string[]> = {
  image: ["image/jpeg", "image/png", "image/webp", "image/gif"],
  video: ["video/mp4", "video/quicktime", "video/webm"],
}

/** Khoá lỗi, dịch ở messages/vi.json (media.errors.*). */
export type UploadErrorKey = "tooLarge" | "badType" | "tooLong" | "uploadFailed" | "aborted"

export class UploadError extends Error {
  constructor(public readonly key: UploadErrorKey) {
    super(key)
  }
}

/** Đoán loại file theo kiểu MIME; không phải ảnh/video được phép thì trả null. */
export function kindOf(file: File): MediaKind | null {
  for (const kind of ["image", "video"] as const) {
    if (ALLOWED_TYPES[kind].includes(file.type)) return kind
  }
  return null
}

/** Kiểm tra nhanh ở trình duyệt trước khi tải lên: trả khoá lỗi hoặc null nếu ổn. */
export function checkFile(file: File, kind: MediaKind): string | null {
  if (!ALLOWED_TYPES[kind].includes(file.type)) return "badType"
  if (file.size > MAX_BYTES[kind]) return "tooLarge"
  return null
}

/** Đọc độ dài video (giây) bằng thẻ <video>; quá 3 phút thì từ chối. */
export function videoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video")
    const url = URL.createObjectURL(file)
    const done = () => URL.revokeObjectURL(url)
    video.preload = "metadata"
    video.onloadedmetadata = () => {
      done()
      if (video.duration > MAX_VIDEO_SECONDS) reject(new UploadError("tooLong"))
      else resolve(video.duration)
    }
    video.onerror = () => {
      done()
      reject(new UploadError("badType"))
    }
    video.src = url
  })
}

export type Storage = "cloudinary" | "drive"

type Options = {
  projectId: string
  /** Nơi lưu của dự án; mặc định Cloudinary. */
  storage?: Storage
  onProgress?: (percent: number) => void
  signal?: AbortSignal
}

type CloudinaryReply = { secure_url: string; public_id: string }

/** Gửi một FormData bằng XHR (để có tiến độ) và trả nội dung JSON. `failure` đổi mã HTTP lỗi thành khoá lỗi. */
function sendForm<T>(
  url: string,
  form: FormData,
  options: Options,
  failure: (status: number) => UploadErrorKey = () => "uploadFailed",
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open("POST", url)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) options.onProgress?.(Math.round((event.loaded / event.total) * 100))
    }
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) return reject(new UploadError(failure(xhr.status)))
      try {
        resolve(JSON.parse(xhr.responseText) as T)
      } catch {
        reject(new UploadError("uploadFailed"))
      }
    }
    xhr.onerror = () => reject(new UploadError("uploadFailed"))
    xhr.onabort = () => reject(new UploadError("aborted"))
    options.signal?.addEventListener("abort", () => xhr.abort())
    xhr.send(form)
  })
}

function driveFailure(status: number): UploadErrorKey {
  if (status === 413) return "tooLarge"
  if (status === 415) return "badType"
  return "uploadFailed"
}

/**
 * Tải file lên nơi lưu của dự án.
 * - Cloudinary: xin backend chữ ký rồi đẩy thẳng lên Cloudinary.
 * - Drive: gửi file tới backend, backend đẩy lên Drive rồi trả lại link.
 */
export async function uploadMedia(file: File, options: Options): Promise<Media> {
  const kind = kindOf(file)
  if (kind === null) throw new UploadError("badType")
  const problem = checkFile(file, kind)
  if (problem) throw new UploadError(problem as UploadErrorKey)
  if (kind === "video") await videoDuration(file)

  if (options.storage === "drive") {
    const form = new FormData()
    form.set("file", file)
    form.set("purpose", "guide")
    return sendForm<Media>(
      `/api/projects/${encodeURIComponent(options.projectId)}/media/upload`,
      form,
      options,
      driveFailure,
    )
  }

  const signed = unwrap(
    await api.POST("/api/projects/{project_id}/media/sign", {
      params: { path: { project_id: options.projectId } },
      body: { kind, purpose: "guide" },
    }),
  )

  const form = new FormData()
  form.set("file", file)
  form.set("api_key", signed.api_key)
  form.set("timestamp", String(signed.timestamp))
  form.set("signature", signed.signature)
  form.set("folder", signed.folder)
  form.set("public_id", signed.public_id)
  form.set("allowed_formats", signed.allowed_formats)

  const reply = await sendForm<CloudinaryReply>(signed.upload_url, form, options)
  return { kind, url: reply.secure_url, public_id: reply.public_id, note: "" }
}

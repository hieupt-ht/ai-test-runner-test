import type { Media } from "@/lib/api/types"

// Khớp với backend: bằng chứng gồm tối đa 1 video và 20 ảnh
export const MAX_EVIDENCE_IMAGES = 20
const ASSIGNEE_PATTERN = /^([A-Za-z0-9]+(-[A-Za-z0-9]+)*)?$/

/** Bỏ khoảng trắng và dấu @ ở đầu (người dùng hay gõ @tên). */
export function normalizeAssignee(value: string): string {
  return value.trim().replace(/^@/, "")
}

/** Tên GitHub hợp lệ (tối đa 39 ký tự) hoặc để trống. */
export function isValidAssignee(value: string): boolean {
  return value.length <= 39 && ASSIGNEE_PATTERN.test(value)
}

/** Giữ lại 1 video đầu tiên và tối đa 20 ảnh, thứ tự như người dùng thêm. */
export function limitEvidence(items: Media[]): Media[] {
  let videos = 0
  let images = 0
  return items.filter((item) => {
    if (item.kind === "video") return ++videos <= 1
    return ++images <= MAX_EVIDENCE_IMAGES
  })
}

/** Tách danh sách bằng chứng thành video (nếu có) và các ảnh, đúng dạng backend nhận. */
export function splitEvidence(items: Media[]): { video: Media | null; screenshots: Media[] } {
  return {
    video: items.find((item) => item.kind === "video") ?? null,
    screenshots: items.filter((item) => item.kind === "image"),
  }
}

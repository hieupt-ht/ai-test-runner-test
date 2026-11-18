import type { Media } from "@/lib/api/types"

const DRIVE_PREFIX = "https://drive.google.com/file/d/"

/** File nằm trên Google Drive (nhận ra từ link). */
export function isDrive(media: Media): boolean {
  return media.url.startsWith(DRIVE_PREFIX)
}

/** Link để đặt vào thẻ <img>. Khớp display_url ở backend (app/core/models/media.py). */
export function displayUrl(media: Media): string {
  if (isDrive(media) && media.kind === "image") {
    return `https://drive.google.com/thumbnail?id=${media.public_id}&sz=w1600`
  }
  return media.url
}

/** Link nhúng bằng <iframe> cho video Drive; Drive không cho phát thẳng bằng thẻ <video>. */
export function embedUrl(media: Media): string | null {
  if (isDrive(media) && media.kind === "video") {
    return `${DRIVE_PREFIX}${media.public_id}/preview`
  }
  return null
}

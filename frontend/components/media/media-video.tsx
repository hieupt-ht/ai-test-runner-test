import type { Media } from "@/lib/api/types"
import { embedUrl } from "@/lib/media/display"

type Props = { media: Media; className?: string }

/** Phát video: Drive không cho phát bằng thẻ <video> nên nhúng iframe; Cloudinary dùng <video>. */
export function MediaVideo({ media, className }: Props) {
  const embed = embedUrl(media)
  if (embed) {
    return <iframe src={embed} allow="autoplay" allowFullScreen className={className} />
  }
  return <video src={media.url} controls preload="metadata" className={className} />
}

"use client"

import { useTranslations } from "next-intl"

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import type { Media } from "@/lib/api/types"
import { displayUrl } from "@/lib/media/display"

type Props = {
  media: Media | null
  onClose: () => void
}

/** Xem ảnh ở cỡ lớn trong một hộp thoại. */
export function MediaLightbox({ media, onClose }: Props) {
  const t = useTranslations("media")
  return (
    <Dialog open={media !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-4xl">
        <DialogTitle className="sr-only">{t("viewLarge")}</DialogTitle>
        {media && (
          // eslint-disable-next-line @next/next/no-img-element -- ảnh ngoài (Cloudinary/Drive)
          <img
            src={displayUrl(media)}
            alt={media.note || t("imageAlt")}
            className="max-h-[80dvh] w-full object-contain"
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

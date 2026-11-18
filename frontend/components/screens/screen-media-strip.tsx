"use client"

import { useTranslations } from "next-intl"
import { useState } from "react"

import { MediaLightbox } from "@/components/media/media-lightbox"
import { MediaVideo } from "@/components/media/media-video"
import type { Media } from "@/lib/api/types"
import { displayUrl } from "@/lib/media/display"

/** Hàng ảnh/video nhỏ của màn hình để tester hình dung. Ảnh bấm vào để xem lớn. */
export function ScreenMediaStrip({ media }: { media: Media[] }) {
  const t = useTranslations("media")
  const [zoomed, setZoomed] = useState<Media | null>(null)
  if (media.length === 0) return null

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {media.map((item) =>
          item.kind === "video" ? (
            <MediaVideo
              key={item.public_id}
              media={item}
              className="h-28 w-44 rounded-md border bg-black"
            />
          ) : (
            <button
              key={item.public_id}
              type="button"
              aria-label={item.note || t("viewLarge")}
              onClick={() => setZoomed(item)}
              className="overflow-hidden rounded-md border"
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- ảnh ngoài (Cloudinary/Drive) */}
              <img
                src={displayUrl(item)}
                alt={item.note || t("imageAlt")}
                className="h-28 w-auto object-cover"
              />
            </button>
          ),
        )}
      </div>
      <MediaLightbox media={zoomed} onClose={() => setZoomed(null)} />
    </>
  )
}

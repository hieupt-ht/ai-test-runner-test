"use client"

import { ImagePlus, Trash2 } from "lucide-react"
import { useTranslations } from "next-intl"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { MediaLightbox } from "@/components/media/media-lightbox"
import { MediaVideo } from "@/components/media/media-video"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { Media } from "@/lib/api/types"
import { displayUrl } from "@/lib/media/display"
import { type Storage, UploadError, uploadMedia } from "@/lib/media/upload"

type Props = {
  value: Media[]
  onChange: (next: Media[]) => void
  max?: number
  projectId: string
  /** Nơi lưu của dự án (mặc định Cloudinary). */
  storage?: Storage
  disabled?: boolean
  /** Báo cho form biết đang tải lên (để khoá nút Lưu/Gửi). */
  onBusyChange?: (busy: boolean) => void
}

type Pending = { id: number; name: string; percent: number }

/** Ô chọn ảnh/video: tải lên Cloudinary hoặc Drive, xem trước, ghi chú ngắn, xoá. */
export function MediaPicker({
  value,
  onChange,
  max = 5,
  projectId,
  storage = "cloudinary",
  disabled,
  onBusyChange,
}: Props) {
  const t = useTranslations("media")
  const inputRef = useRef<HTMLInputElement>(null)
  const [pending, setPending] = useState<Pending[]>([])
  const [zoomed, setZoomed] = useState<Media | null>(null)
  // Giữ danh sách mới nhất: tải xong sau vài giây thì không ghi đè mục vừa thêm/xoá.
  const latest = useRef(value)
  const nextId = useRef(0)

  useEffect(() => {
    latest.current = value
  }, [value])

  useEffect(() => {
    onBusyChange?.(pending.length > 0)
  }, [pending.length, onBusyChange])

  const full = value.length + pending.length >= max

  async function upload(file: File) {
    const id = nextId.current++
    setPending((list) => [...list, { id, name: file.name, percent: 0 }])
    try {
      const uploaded = await uploadMedia(file, {
        projectId,
        storage,
        onProgress: (percent) =>
          setPending((list) => list.map((item) => (item.id === id ? { ...item, percent } : item))),
      })
      onChange([...latest.current, uploaded])
    } catch (error) {
      const key = error instanceof UploadError ? error.key : "uploadFailed"
      toast.error(`${file.name}: ${t(`errors.${key}`)}`)
    } finally {
      setPending((list) => list.filter((item) => item.id !== id))
    }
  }

  function pick(files: FileList | null) {
    if (!files) return
    const room = max - value.length - pending.length
    for (const file of Array.from(files).slice(0, Math.max(room, 0))) void upload(file)
    if (inputRef.current) inputRef.current.value = "" // cho phép chọn lại đúng file đó
  }

  return (
    <div className="flex flex-col gap-2">
      {value.map((item, index) => (
        <div key={item.public_id} className="flex gap-2 rounded-lg border p-2">
          {item.kind === "image" ? (
            <button
              type="button"
              aria-label={t("viewLarge")}
              className="shrink-0"
              onClick={() => setZoomed(item)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- ảnh ngoài (Cloudinary/Drive) */}
              <img
                src={displayUrl(item)}
                alt={item.note || t("imageAlt")}
                className="size-16 rounded object-cover"
              />
            </button>
          ) : (
            <MediaVideo media={item} className="h-16 w-28 rounded" />
          )}
          <Input
            value={item.note}
            maxLength={200}
            disabled={disabled}
            placeholder={t("notePlaceholder")}
            onChange={(event) =>
              onChange(
                value.map((entry, i) => (i === index ? { ...entry, note: event.target.value } : entry)),
              )
            }
          />
          {!disabled && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={t("remove")}
              onClick={() => onChange(value.filter((_, i) => i !== index))}
            >
              <Trash2 />
            </Button>
          )}
        </div>
      ))}

      {pending.map((item) => (
        <div key={item.id} className="flex flex-col gap-1 rounded-lg border p-2 text-xs">
          <span className="truncate">{item.name}</span>
          <div
            role="progressbar"
            aria-valuenow={item.percent}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-1.5 overflow-hidden rounded bg-muted"
          >
            <div className="h-full bg-primary" style={{ width: `${item.percent}%` }} />
          </div>
        </div>
      ))}

      {!disabled && !full && (
        <>
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/webm"
            onChange={(event) => pick(event.target.files)}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="self-start"
            onClick={() => inputRef.current?.click()}
          >
            <ImagePlus /> {t("add")}
          </Button>
        </>
      )}

      <MediaLightbox media={zoomed} onClose={() => setZoomed(null)} />
    </div>
  )
}

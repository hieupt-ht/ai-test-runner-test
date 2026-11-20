"use client"

import { ChevronDown, Pause, Play } from "lucide-react"
import { useTranslations } from "next-intl"
import { useEffect, useRef, useState } from "react"

import { useMusic } from "@/components/music/music-provider"
import { Button } from "@/components/ui/button"
import { TRACKS } from "@/lib/music/tracks"

/** Nút phát/dừng nhạc ở thanh đầu trang, kèm menu nhỏ (tên bài, bài tiếp, âm lượng). */
export function MusicButton() {
  const t = useTranslations("music")
  const music = useMusic()
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  // Bấm ra ngoài hoặc nhấn Esc thì đóng menu nhỏ
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onClick)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onClick)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  if (!music) return null

  return (
    <div ref={boxRef} className="relative flex items-center">
      <Button
        type="button"
        size="icon"
        variant={music.playing ? "default" : "outline"}
        className="rounded-full"
        aria-label={music.playing ? t("pause") : t("play")}
        onClick={music.toggle}
      >
        {music.playing ? <Pause /> : <Play />}
      </Button>
      <Button
        type="button"
        size="icon-sm"
        variant="ghost"
        aria-label={t("options")}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <ChevronDown />
      </Button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-56 space-y-3 rounded-lg bg-popover p-3 text-popover-foreground shadow-md ring-1 ring-foreground/10">
          <p className="truncate text-sm font-medium">{TRACKS[music.track]?.title}</p>
          <Button type="button" size="sm" variant="outline" onClick={music.next}>
            {t("next")}
          </Button>
          <label className="block space-y-1 text-xs text-muted-foreground">
            {t("volume")}
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={music.volume}
              onChange={(e) => music.setVolume(Number(e.target.value))}
              className="w-full accent-primary"
            />
          </label>
        </div>
      )}
    </div>
  )
}

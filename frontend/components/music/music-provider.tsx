"use client"

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react"

import { TRACKS } from "@/lib/music/tracks"

export type MusicContextValue = {
  playing: boolean
  track: number
  volume: number
  toggle: () => void
  next: () => void
  setVolume: (v: number) => void
}

const MusicContext = createContext<MusicContextValue | null>(null)

/** Ngoài MusicProvider thì trả về null (để nút nhạc tự ẩn). */
export function useMusic(): MusicContextValue | null {
  return useContext(MusicContext)
}

const VOLUME_KEY = "music:volume"
const TRACK_KEY = "music:track"
const DEFAULT_VOLUME = 0.4

// localStorage có thể bị chặn (cửa sổ ẩn danh...) nên mọi lần đọc/ghi đều bọc try/catch
function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStored(key: string, value: string) {
  try {
    localStorage.setItem(key, String(value))
  } catch {
    // Không lưu được cũng không sao, chỉ là lần sau mất cài đặt
  }
}

function readVolume(): number {
  const raw = readStored(VOLUME_KEY)
  if (raw === null) return DEFAULT_VOLUME
  const value = Number(raw)
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : DEFAULT_VOLUME
}

function readTrack(): number {
  const value = Number(readStored(TRACK_KEY))
  return Number.isInteger(value) && value >= 0 && value < TRACKS.length ? value : 0
}

/**
 * Một thẻ <audio> duy nhất cho cả ứng dụng. Đặt ngoài AppShell nên chuyển trang thì nhạc không ngắt.
 * Không bao giờ tự phát; tải lại trang luôn ở trạng thái dừng.
 */
export function MusicProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [track, setTrack] = useState(0)
  const [volume, setVolumeState] = useState(DEFAULT_VOLUME)

  // Đọc cài đặt đã lưu sau khi trang hiện ra (tránh lệch giữa server và client)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- đọc localStorage chỉ làm được ở client
    setVolumeState(readVolume())
    setTrack(readTrack())
  }, [])

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = volume
  }, [volume])

  function toggle() {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
      setPlaying(false)
      return
    }
    // Trình duyệt có thể từ chối phát; khi đó giữ trạng thái dừng
    audio
      .play()
      .then(() => setPlaying(true))
      .catch(() => setPlaying(false))
  }

  function goTo(index: number) {
    setTrack(index)
    writeStored(TRACK_KEY, String(index))
    // Đổi bài khi đang phát thì phát tiếp bài mới sau khi src đổi xong
    if (playing) {
      requestAnimationFrame(() => {
        audioRef.current?.play().catch(() => setPlaying(false))
      })
    }
  }

  function next() {
    goTo((track + 1) % TRACKS.length)
  }

  function setVolume(v: number) {
    const clamped = Math.min(1, Math.max(0, v))
    setVolumeState(clamped)
    writeStored(VOLUME_KEY, String(clamped))
  }

  return (
    <MusicContext.Provider value={{ playing, track, volume, toggle, next, setVolume }}>
      {children}
      {/* preload="none": chưa bấm phát thì chưa tải file nào */}
      <audio
        ref={audioRef}
        src={TRACKS[track].src}
        preload="none"
        onEnded={next}
        // Nhạc bị dừng/phát từ bên ngoài (phím media, rút tai nghe...) thì nút theo kịp
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />
    </MusicContext.Provider>
  )
}

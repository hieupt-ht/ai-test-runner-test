"use client"

import { useId } from "react"
import { useTranslations } from "next-intl"

import type { PetMood } from "@/lib/api/types"

import "./hedgehog.css"

type Level = 1 | 2 | 3 | 4

// Cấp càng cao càng to, gai càng nhiều và càng dài (rIn nhỏ = gai dài)
const SIZE: Record<Level, { width: number; spikes: number; inner: number }> = {
  1: { width: 96, spikes: 11, inner: 0.84 },
  2: { width: 128, spikes: 13, inner: 0.8 },
  3: { width: 160, spikes: 15, inner: 0.76 },
  4: { width: 192, spikes: 17, inner: 0.72 },
}

// Màu thân nhím là ngoại lệ duy nhất không lấy từ biến giao diện (cùng một con nhím ở mọi giao diện)
const COLOR = {
  spikeStroke: "#7B55B8",
  spikeDark: "#5B3A8C",
  ear: "#FFC2D9",
  blush: "#FF8FC0",
  eye: "#22163A",
}

/** Đường răng cưa quanh một hình elip = bộ gai. */
function spikePath(cx: number, cy: number, rx: number, ry: number, inner: number, count: number) {
  let d = ""
  for (let i = 0; i <= count * 2; i++) {
    const angle = Math.PI + (i / (count * 2)) * Math.PI * 1.25 - Math.PI * 0.125
    const k = i % 2 === 0 ? inner : 1
    const x = cx + Math.cos(angle) * rx * k
    const y = cy + Math.sin(angle) * ry * k
    d += `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)} `
  }
  return `${d}Z`
}

const LINE = { fill: "none", stroke: COLOR.eye, strokeLinecap: "round" } as const

/** Mắt + miệng + phần phụ theo biểu cảm. */
function Face({ mood }: { mood: PetMood }) {
  const E = COLOR.eye
  if (mood === "HAPPY") {
    return (
      <>
        <g>
          <path d="M74 101 Q82 91 90 101" strokeWidth={4} {...LINE} />
          <path d="M110 101 Q118 91 126 101" strokeWidth={4} {...LINE} />
        </g>
        <path d="M91 118 Q100 134 109 118 Z" fill={E} />
        <path d="M95 125 Q100 131 105 125 Z" fill="#FF6F8E" />
        <text x="150" y="52" fontSize="18">✨</text>
        <text x="34" y="60" fontSize="14">✨</text>
      </>
    )
  }
  if (mood === "NORMAL") {
    return (
      <>
        <g className="hh-blink">
          <circle cx="82" cy="100" r="7" fill={E} />
          <circle cx="84.5" cy="97.5" r="2.5" fill="#fff" />
          <circle cx="118" cy="100" r="7" fill={E} />
          <circle cx="120.5" cy="97.5" r="2.5" fill="#fff" />
        </g>
        <path d="M94 121 Q100 127 106 121" strokeWidth={3} {...LINE} />
      </>
    )
  }
  if (mood === "HUNGRY") {
    return (
      <>
        <g className="hh-blink">
          <circle cx="82" cy="100" r="9" fill={E} />
          <circle cx="84" cy="95" r="3.5" fill="#fff" />
          <circle cx="79" cy="103" r="1.5" fill="#fff" />
          <circle cx="118" cy="100" r="9" fill={E} />
          <circle cx="120" cy="95" r="3.5" fill="#fff" />
          <circle cx="115" cy="103" r="1.5" fill="#fff" />
        </g>
        <ellipse cx="100" cy="124" rx="4.5" ry="5.5" fill={E} />
        <path d="M104 127 Q106 135 104 138 Q101 135 104 127 Z" fill="#8FD3FF" />
        <circle cx="158" cy="42" r="17" fill="#fff" stroke="#ddd" />
        <circle cx="142" cy="62" r="4" fill="#fff" stroke="#ddd" />
        <text x="148" y="49" fontSize="18">🐞</text>
      </>
    )
  }
  // CRY
  return (
    <>
      <path d="M72 88 L90 93" strokeWidth={3} {...LINE} />
      <path d="M128 88 L110 93" strokeWidth={3} {...LINE} />
      <path d="M74 99 Q82 107 90 99" strokeWidth={4} {...LINE} />
      <path d="M110 99 Q118 107 126 99" strokeWidth={4} {...LINE} />
      <path d="M92 127 Q100 118 108 127" strokeWidth={3} {...LINE} />
      <path d="M78 106 Q72 118 78 124 Q84 118 78 106 Z" fill="#7CC8FF" />
      <path d="M122 106 Q116 118 122 124 Q128 118 122 106 Z" fill="#7CC8FF" />
    </>
  )
}

/** Con nhím bug: lớn dần theo cấp (1–4), đổi mặt theo tâm trạng. */
export function Hedgehog({
  level,
  mood,
  className,
}: {
  level: Level
  mood: PetMood
  className?: string
}) {
  const t = useTranslations("pet")
  // id gradient phải khác nhau giữa các con nhím trên cùng một trang
  const id = useId()
  const spikeFill = `${id}-spike`
  const faceFill = `${id}-face`
  const size = SIZE[level]
  const label = t("alt", { level: t(`level.${level}`), mood: t(`mood.${mood}`) })

  return (
    <svg
      role="img"
      aria-label={label}
      viewBox="0 0 200 170"
      width={size.width}
      height={Math.round((size.width * 170) / 200)}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <radialGradient id={spikeFill} cx="40%" cy="30%" r="75%">
          <stop offset="0" stopColor="#B58CFF" />
          <stop offset="1" stopColor={COLOR.spikeDark} />
        </radialGradient>
        <radialGradient id={faceFill} cx="45%" cy="35%" r="70%">
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#FFE3F1" />
        </radialGradient>
      </defs>
      <ellipse cx="100" cy="160" rx="55" ry="7" fill="#000" opacity=".08" />
      <g className="hh-bounce">
        <path
          d={spikePath(100, 96, 88, 78, size.inner, size.spikes)}
          fill={`url(#${spikeFill})`}
          stroke={COLOR.spikeStroke}
          strokeWidth={6}
          strokeLinejoin="round"
        />
        <ellipse cx="72" cy="52" rx="22" ry="9" fill="#fff" opacity=".35" transform="rotate(-25 72 52)" />
        <circle cx="64" cy="70" r="11" fill={`url(#${faceFill})`} />
        <circle cx="64" cy="70" r="5.5" fill={COLOR.ear} />
        <circle cx="136" cy="70" r="11" fill={`url(#${faceFill})`} />
        <circle cx="136" cy="70" r="5.5" fill={COLOR.ear} />
        <ellipse cx="100" cy="108" rx="52" ry="44" fill={`url(#${faceFill})`} />
        <ellipse cx="78" cy="152" rx="13" ry="8" fill={COLOR.spikeStroke} />
        <ellipse cx="122" cy="152" rx="13" ry="8" fill={COLOR.spikeStroke} />
        <ellipse cx="68" cy="117" rx="9" ry="5.5" fill={COLOR.blush} opacity=".6" />
        <ellipse cx="132" cy="117" rx="9" ry="5.5" fill={COLOR.blush} opacity=".6" />
        <Face mood={mood} />
        <ellipse cx="100" cy="112" rx="6" ry="4.5" fill={COLOR.eye} />
        {level === 4 && (
          <g data-testid="crown">
            <path d="M80 62 L84 38 L92 52 L100 32 L108 52 L116 38 L120 62 Z" fill="#FFD23F" stroke="#E0A800" strokeWidth={3} strokeLinejoin="round" />
            <circle cx="100" cy="32" r="3.5" fill="#FF6F8E" />
          </g>
        )}
      </g>
    </svg>
  )
}

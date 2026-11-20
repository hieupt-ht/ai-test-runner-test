import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { MusicButton } from "@/components/music/music-button"
import type { MusicContextValue } from "@/components/music/music-provider"
import messages from "@/messages/vi.json"

const mocks = vi.hoisted(() => ({ music: null as unknown }))

vi.mock("@/components/music/music-provider", () => ({
  useMusic: () => mocks.music,
}))

afterEach(() => {
  cleanup()
  mocks.music = null
})

function fakeMusic(over: Partial<MusicContextValue> = {}): MusicContextValue {
  return { playing: false, track: 0, volume: 0.4, toggle: vi.fn(), next: vi.fn(), setVolume: vi.fn(), ...over }
}

function renderButton() {
  return render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <MusicButton />
    </NextIntlClientProvider>,
  )
}

describe("MusicButton", () => {
  it("bấm nút thì gọi toggle và đổi nhãn", () => {
    const music = fakeMusic()
    mocks.music = music
    const { rerender } = renderButton()

    fireEvent.click(screen.getByRole("button", { name: "Phát nhạc" }))
    expect(music.toggle).toHaveBeenCalledTimes(1)

    // Khi đang phát thì nhãn đổi thành "Dừng nhạc"
    mocks.music = fakeMusic({ playing: true })
    rerender(
      <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
        <MusicButton />
      </NextIntlClientProvider>,
    )
    expect(screen.getByRole("button", { name: "Dừng nhạc" })).toBeInTheDocument()
  })

  it("ngoài MusicProvider thì không hiện gì", () => {
    mocks.music = null
    const { container } = renderButton()
    expect(container).toBeEmptyDOMElement()
  })

  it("mở menu nhỏ thì thấy tên bài, bấm Bài tiếp và kéo âm lượng", () => {
    const music = fakeMusic()
    mocks.music = music
    renderButton()

    fireEvent.click(screen.getByRole("button", { name: "Tùy chọn nhạc" }))
    expect(screen.getByText("Chill lofi")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Bài tiếp" }))
    expect(music.next).toHaveBeenCalledTimes(1)

    fireEvent.change(screen.getByLabelText("Âm lượng"), { target: { value: "0.7" } })
    expect(music.setVolume).toHaveBeenCalledWith(0.7)
  })
})

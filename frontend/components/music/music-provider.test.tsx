import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { MusicProvider, useMusic } from "@/components/music/music-provider"
import { TRACKS } from "@/lib/music/tracks"

const play = vi.fn()
const pause = vi.fn()

// Component nhỏ để đọc giá trị trong context ra màn hình và có nút để bấm thử
function Probe() {
  const music = useMusic()
  if (!music) return <p>ngoai-provider</p>
  return (
    <div>
      <span data-testid="state">
        {music.playing ? "dang-phat" : "dung"}|{music.track}|{music.volume}
      </span>
      <button onClick={music.toggle}>toggle</button>
      <button onClick={music.next}>next</button>
      <button onClick={() => music.setVolume(0.8)}>vol</button>
    </div>
  )
}

function renderProvider() {
  return render(
    <MusicProvider>
      <Probe />
    </MusicProvider>,
  )
}

const state = () => screen.getByTestId("state").textContent

beforeEach(() => {
  play.mockReset().mockResolvedValue(undefined)
  pause.mockReset()
  window.HTMLMediaElement.prototype.play = play
  window.HTMLMediaElement.prototype.pause = pause
  localStorage.clear()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe("MusicProvider", () => {
  it("không tự phát khi mở trang", () => {
    const { container } = renderProvider()
    expect(play).not.toHaveBeenCalled()
    expect(container.querySelectorAll("audio")).toHaveLength(1)
    expect(container.querySelector("audio")?.getAttribute("preload")).toBe("none")
    expect(state()).toBe("dung|0|0.4")
  })

  it("nhạc bị dừng từ bên ngoài (phím media, rút tai nghe) thì nút về trạng thái dừng", async () => {
    const { container } = renderProvider()
    await act(async () => screen.getByText("toggle").click())
    expect(state()).toBe("dang-phat|0|0.4")

    fireEvent.pause(container.querySelector("audio")!)
    expect(state()).toBe("dung|0|0.4")
    fireEvent.play(container.querySelector("audio")!)
    expect(state()).toBe("dang-phat|0|0.4")
  })

  it("toggle phát rồi dừng", async () => {
    renderProvider()
    await act(async () => screen.getByText("toggle").click())
    expect(play).toHaveBeenCalledTimes(1)
    expect(state()).toContain("dang-phat")

    await act(async () => screen.getByText("toggle").click())
    expect(pause).toHaveBeenCalled()
    expect(state()).toContain("dung")
  })

  it("next quay vòng danh sách bài", async () => {
    renderProvider()
    for (let i = 0; i < TRACKS.length; i++) {
      await act(async () => screen.getByText("next").click())
    }
    // Bấm đủ số bài thì quay lại bài đầu
    expect(state()).toContain("|0|")
  })

  it("nhớ âm lượng sau khi tải lại", async () => {
    const first = renderProvider()
    await act(async () => screen.getByText("vol").click())
    expect(state()).toContain("|0.8")
    first.unmount()

    renderProvider()
    expect(state()).toContain("|0.8")
  })

  it("localStorage bị chặn vẫn chạy được", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked")
    })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked")
    })
    renderProvider()
    expect(state()).toBe("dung|0|0.4")
    await act(async () => screen.getByText("vol").click())
    expect(state()).toContain("|0.8")
  })

  it("play bị trình duyệt từ chối thì về trạng thái dừng", async () => {
    play.mockRejectedValue(new Error("NotAllowedError"))
    renderProvider()
    await act(async () => screen.getByText("toggle").click())
    expect(state()).toContain("dung")
  })

  it("ngoài provider thì useMusic trả null", () => {
    render(<Probe />)
    expect(screen.getByText("ngoai-provider")).toBeInTheDocument()
  })
})

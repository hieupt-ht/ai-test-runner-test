import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { NextIntlClientProvider } from "next-intl"
import { afterEach, describe, expect, it, vi } from "vitest"

import { StepsEditor } from "@/components/test-cases/steps-editor"
import type { TestStep } from "@/lib/api/types"
import messages from "@/messages/vi.json"

afterEach(cleanup)

function renderEditor(
  steps: TestStep[],
  props: { onChange?: (steps: TestStep[]) => void; disabled?: boolean; errors?: object[] } = {},
) {
  const onChange = props.onChange ?? vi.fn()
  render(
    <NextIntlClientProvider locale="vi" messages={messages} timeZone="Asia/Ho_Chi_Minh">
      <StepsEditor steps={steps} onChange={onChange} disabled={props.disabled} errors={props.errors} />
    </NextIntlClientProvider>,
  )
  return onChange
}

const plain: TestStep = { action: "Mở trang", expected: "" }

describe("StepsEditor — phần Tự động", () => {
  it("thu gọn mặc định cho mỗi bước", () => {
    renderEditor([plain, plain])

    const sections = screen.getAllByText("Tự động").map((el) => el.closest("details"))
    expect(sections).toHaveLength(2)
    sections.forEach((details) => expect(details).not.toHaveAttribute("open"))
  })

  it("chọn loại hành động thì tạo phần tự động đúng hình dạng", () => {
    const onChange = renderEditor([plain])

    fireEvent.change(screen.getByLabelText("Hành động tự động 1"), { target: { value: "click" } })

    expect(onChange).toHaveBeenCalledWith([
      { ...plain, auto: { type: "click", value: "", target: { by: "text", value: "" } } },
    ])
  })

  it("loại nhập chữ hiện ô phần tử và ô giá trị", () => {
    renderEditor([
      { ...plain, auto: { type: "fill", value: "", target: { by: "label", value: "" } } },
    ])

    expect(screen.getByLabelText("Tìm theo 1")).toBeInTheDocument()
    expect(screen.getByLabelText("Chữ hiển thị hoặc nhãn 1")).toBeInTheDocument()
    expect(screen.getByLabelText("Giá trị 1")).toBeInTheDocument()
  })

  it("loại mở trang không có ô phần tử; loại bấm không có ô giá trị", () => {
    renderEditor([{ ...plain, auto: { type: "goto", value: "" } }])
    expect(screen.queryByLabelText("Chữ hiển thị hoặc nhãn 1")).not.toBeInTheDocument()
    expect(screen.getByLabelText("Giá trị 1")).toBeInTheDocument()
    cleanup()

    renderEditor([
      { ...plain, auto: { type: "click", value: "", target: { by: "text", value: "Gửi" } } },
    ])
    expect(screen.queryByLabelText("Giá trị 1")).not.toBeInTheDocument()
    expect(screen.getByLabelText("Chữ hiển thị hoặc nhãn 1")).toHaveValue("Gửi")
  })

  it("sửa chữ của phần tử và giá trị gọi onChange với auto mới", () => {
    const step: TestStep = {
      ...plain,
      auto: { type: "fill", value: "", target: { by: "label", value: "" } },
    }
    const onChange = renderEditor([step])

    fireEvent.change(screen.getByLabelText("Chữ hiển thị hoặc nhãn 1"), {
      target: { value: "Email" },
    })
    fireEvent.change(screen.getByLabelText("Giá trị 1"), { target: { value: "qa@x.com" } })

    expect(onChange).toHaveBeenNthCalledWith(1, [
      { ...step, auto: { ...step.auto, target: { by: "label", value: "Email" } } },
    ])
    expect(onChange).toHaveBeenNthCalledWith(2, [
      { ...step, auto: { ...step.auto, value: "qa@x.com" } },
    ])
  })

  it("CSS selector nằm trong mục Nâng cao, đóng cho tới khi mở", () => {
    renderEditor([
      { ...plain, auto: { type: "click", value: "", target: { by: "text", value: "Gửi" } } },
    ])

    const css = screen.getByLabelText("CSS selector 1")
    expect(css).not.toBeVisible()

    const advanced = css.closest("details") as HTMLDetailsElement
    const section = advanced.parentElement?.closest("details") as HTMLDetailsElement
    section.open = true
    expect(css).not.toBeVisible() // mục Nâng cao vẫn đóng
    advanced.open = true
    expect(css).toBeVisible()
  })

  it("nhập CSS đổi cách tìm sang css; xoá CSS quay về cách tìm mặc định", () => {
    const step: TestStep = {
      ...plain,
      auto: { type: "click", value: "", target: { by: "text", value: "Gửi" } },
    }
    const onChange = renderEditor([step])

    fireEvent.change(screen.getByLabelText("CSS selector 1"), { target: { value: "#send" } })

    expect(onChange).toHaveBeenCalledWith([
      { ...step, auto: { ...step.auto, target: { by: "css", value: "#send" } } },
    ])
    cleanup()

    const cssStep: TestStep = {
      ...plain,
      auto: { type: "click", value: "", target: { by: "css", value: "#send" } },
    }
    const onChange2 = renderEditor([cssStep])
    expect(screen.queryByLabelText("Chữ hiển thị hoặc nhãn 1")).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText("CSS selector 1"), { target: { value: "" } })

    expect(onChange2).toHaveBeenCalledWith([
      { ...cssStep, auto: { ...cssStep.auto, target: { by: "text", value: "" } } },
    ])
  })

  it("chọn 'Không dùng tự động' bỏ hẳn khoá auto khỏi bước", () => {
    const step: TestStep = { ...plain, auto: { type: "goto", value: "/login" } }
    const onChange = renderEditor([step])

    fireEvent.change(screen.getByLabelText("Hành động tự động 1"), { target: { value: "" } })

    const [steps] = vi.mocked(onChange).mock.calls[0]
    expect(steps[0]).toEqual(plain)
    expect(steps[0]).not.toHaveProperty("auto")
  })

  it("không sửa được khi disabled", () => {
    renderEditor([{ ...plain, auto: { type: "goto", value: "/x" } }], { disabled: true })

    expect(screen.getByLabelText("Hành động tự động 1")).toBeDisabled()
    expect(screen.getByLabelText("Giá trị 1")).toBeDisabled()
  })

  it("hiện lỗi của phần tự động và tự mở phần đó", () => {
    renderEditor([{ ...plain, auto: { type: "goto", value: "" } }], {
      errors: [{ auto: "autoValueRequired" }],
    })

    expect(screen.getByText("Nhập giá trị cho bước tự động")).toBeVisible()
  })
})

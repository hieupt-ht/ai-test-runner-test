import type { AutoStep, AutoType, TestStep } from "@/lib/api/types"

/** Chuyển phần tử từ vị trí `from` sang `to`, trả mảng mới (không sửa mảng gốc). */
export function moveStep<T>(steps: T[], from: number, to: number): T[] {
  const inRange = (i: number) => i >= 0 && i < steps.length
  if (!inRange(from) || !inRange(to) || from === to) return [...steps]
  const result = [...steps]
  const [item] = result.splice(from, 1)
  result.splice(to, 0, item)
  return result
}

/** Chèn một bước trống ngay sau vị trí `index`. */
export function insertStepAfter(steps: TestStep[], index: number): TestStep[] {
  const result = [...steps]
  result.splice(index + 1, 0, { action: "", expected: "" })
  return result
}

/** Xoá một bước; luôn giữ lại tối thiểu 1 bước. */
export function removeStep(steps: TestStep[], index: number): TestStep[] {
  if (steps.length <= 1) return [...steps]
  return steps.filter((_, i) => i !== index)
}

/** Các hành động tự động, đúng thứ tự hiện trong danh sách chọn (khớp backend `AutoType`). */
export const AUTO_TYPES: AutoType[] = [
  "goto",
  "fill",
  "click",
  "select",
  "see_text",
  "not_see_text",
  "url_is",
]

/** Loại bước phải chỉ ra phần tử trên trang. */
export function autoNeedsTarget(type: AutoType): boolean {
  return type === "fill" || type === "click" || type === "select"
}

/** Loại bước bắt buộc có giá trị (nhập chữ được để trống để xoá ô, bấm không cần giá trị). */
export function autoNeedsValue(type: AutoType): boolean {
  return type !== "click" && type !== "fill"
}

/** Loại bước có ô giá trị trên form (mọi loại trừ bấm). */
export function autoHasValueField(type: AutoType): boolean {
  return type !== "click"
}

/** Phần tự động mới, trống, đúng hình dạng của loại bước. */
export function defaultAuto(type: AutoType): AutoStep {
  if (!autoNeedsTarget(type)) return { type, value: "" }
  return { type, value: "", target: { by: type === "click" ? "text" : "label", value: "" } }
}

/** Đã điền đủ phần bắt buộc chưa (phần tử và giá trị). */
export function isAutoComplete(auto: AutoStep): boolean {
  if (autoNeedsTarget(auto.type) && !auto.target?.value.trim()) return false
  if (autoNeedsValue(auto.type) && !auto.value.trim()) return false
  return true
}

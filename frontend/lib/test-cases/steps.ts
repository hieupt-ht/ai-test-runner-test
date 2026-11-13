import type { TestStep } from "@/lib/api/types"

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

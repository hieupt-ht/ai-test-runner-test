import { describe, expect, it } from "vitest"

import type { TestCase } from "@/lib/api/types"
import {
  approvableIds,
  batchItems,
  batchSummary,
  toggleId,
  toggleAll,
} from "@/lib/test-cases/selection"

function make(id: string, status: TestCase["status"], version = 1): TestCase {
  return { id, status, version } as TestCase
}

const cases = [
  make("TC-1", "IN_REVIEW", 2),
  make("TC-2", "DRAFT"),
  make("TC-3", "IN_REVIEW", 5),
  make("TC-4", "APPROVED"),
]

describe("approvableIds", () => {
  it("chỉ lấy case Chờ duyệt, giữ thứ tự", () => {
    expect(approvableIds(cases)).toEqual(["TC-1", "TC-3"])
  })
})

describe("toggleId", () => {
  it("thêm nếu chưa chọn, bỏ nếu đã chọn, không sửa tập cũ", () => {
    const empty = new Set<string>()
    const one = toggleId(empty, "TC-1")
    expect([...one]).toEqual(["TC-1"])
    expect(empty.size).toBe(0)
    expect(toggleId(one, "TC-1").size).toBe(0)
  })
})

describe("toggleAll", () => {
  it("chưa chọn đủ thì chọn tất cả, đã chọn đủ thì bỏ hết", () => {
    const some = new Set(["TC-1"])
    expect([...toggleAll(some, ["TC-1", "TC-3"])].sort()).toEqual(["TC-1", "TC-3"])
    expect(toggleAll(new Set(["TC-1", "TC-3"]), ["TC-1", "TC-3"]).size).toBe(0)
  })

  it("danh sách rỗng thì không chọn gì", () => {
    expect(toggleAll(new Set(), []).size).toBe(0)
  })
})

describe("batchItems", () => {
  it("lấy version hiện tại của từng case đã chọn, bỏ case không còn Chờ duyệt", () => {
    const selected = new Set(["TC-3", "TC-2", "TC-1", "TC-404"])
    expect(batchItems(selected, cases)).toEqual([
      { case_id: "TC-1", version: 2 },
      { case_id: "TC-3", version: 5 },
    ])
  })
})

describe("batchSummary", () => {
  it("gom số duyệt được và số bỏ qua", () => {
    expect(batchSummary({ approved: [make("TC-1", "APPROVED")], skipped: [] })).toEqual({
      approved: 1,
      skipped: 0,
    })
    expect(
      batchSummary({ approved: [], skipped: [{ case_id: "TC-2", reason: "x" }] }),
    ).toEqual({ approved: 0, skipped: 1 })
  })
})

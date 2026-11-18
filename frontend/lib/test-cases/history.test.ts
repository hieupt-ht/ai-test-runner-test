import { describe, expect, it } from "vitest"

import { changedLabels, formatVietnamTime, versionOfEntry } from "@/lib/test-cases/history"

describe("history", () => {
  it("đổi giờ UTC sang giờ Việt Nam dạng 16/11/2026 14:05", () => {
    expect(formatVietnamTime("2026-11-16T07:05:00Z")).toBe("16/11/2026 14:05")
  })

  it("dịch tên trường đã đổi và bỏ trường lạ", () => {
    expect(changedLabels({ steps: [], platform: [], comment: "x", lạ: 1 })).toEqual([
      "Các bước",
      "Nền tảng",
    ])
  })

  it("trường execution_mode hiện là Cách chạy", () => {
    expect(changedLabels({ execution_mode: ["MANUAL", "AUTOMATION"] })).toEqual(["Cách chạy"])
  })

  it("mỗi dòng lịch sử là một phiên bản, đếm từ cũ nhất", () => {
    expect(versionOfEntry(0, 3)).toBe(3) // dòng mới nhất của 3 dòng là v3
    expect(versionOfEntry(2, 3)).toBe(1)
  })
})

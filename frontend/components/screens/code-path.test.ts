import { describe, expect, it } from "vitest"

import { codePathError } from "@/components/screens/code-path"

describe("codePathError", () => {
  it("chấp nhận đường dẫn tương đối trong repo", () => {
    expect(codePathError("src/pages/login.tsx")).toBeNull()
    expect(codePathError("  api/auth/ ")).toBeNull()
  })

  it.each([
    ["/etc/passwd", "absolute"],
    ["../secret", "dotdot"],
    ["src/../x", "dotdot"],
    ["a\\b", "backslash"],
    ["", "empty"],
    ["x".repeat(201), "tooLong"],
  ])("báo lỗi với %s", (path, expected) => {
    expect(codePathError(path)).toBe(expected)
  })
})

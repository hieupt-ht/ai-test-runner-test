// Cùng quy tắc với backend (app/core/models/screen.py): đường dẫn tương đối trong repo.
export const MAX_CODE_PATHS = 20
const MAX_LENGTH = 200

export type CodePathError = "empty" | "tooLong" | "absolute" | "backslash" | "dotdot"

/** Trả về mã lỗi (để tra câu báo trong vi.json), hoặc null nếu đường dẫn hợp lệ. */
export function codePathError(rawPath: string): CodePathError | null {
  const path = rawPath.trim()
  if (!path) return "empty"
  if (path.length > MAX_LENGTH) return "tooLong"
  if (path.startsWith("/")) return "absolute"
  if (path.includes("\\")) return "backslash"
  if (path.split("/").includes("..")) return "dotdot"
  return null
}

/** Chỉ cho phép link http/https; các kiểu khác (như javascript:) trả về null để không tạo link. */
export function safeEvidenceUrl(value: string): string | null {
  try {
    const url = new URL(value)
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null
  } catch {
    return null
  }
}

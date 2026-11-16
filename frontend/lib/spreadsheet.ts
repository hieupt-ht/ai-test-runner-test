// Cùng quy tắc với backend (app/core/sheets/spreadsheet_id.py), để báo lỗi ngay khi gõ.
const ID = "[A-Za-z0-9_-]{20,}"
const FROM_LINK = new RegExp(`/spreadsheets/d/(${ID})`)
const BARE_ID = new RegExp(`^${ID}$`)

export function parseSpreadsheetInput(text: string): string | null {
  const cleaned = text.trim()
  const fromLink = FROM_LINK.exec(cleaned)
  if (fromLink) return fromLink[1] ?? null
  return BARE_ID.test(cleaned) ? cleaned : null
}

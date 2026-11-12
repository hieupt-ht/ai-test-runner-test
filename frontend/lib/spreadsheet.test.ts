import { describe, expect, it } from "vitest"

import { parseSpreadsheetInput } from "@/lib/spreadsheet"

const SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"

describe("parseSpreadsheetInput", () => {
  it("tách ID từ link Google Sheet đầy đủ và bỏ khoảng trắng", () => {
    expect(parseSpreadsheetInput(`  https://docs.google.com/spreadsheets/d/${SHEET_ID}/edit#gid=0 `)).toBe(SHEET_ID)
    expect(parseSpreadsheetInput(SHEET_ID)).toBe(SHEET_ID)
  })

  it("trả null với chuỗi không phải Sheet", () => {
    expect(parseSpreadsheetInput("")).toBeNull()
    expect(parseSpreadsheetInput("abc")).toBeNull()
    expect(parseSpreadsheetInput("https://example.com/x")).toBeNull()
  })
})

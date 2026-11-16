"""Lấy Spreadsheet ID từ thứ người dùng dán vào: ID trần, hoặc cả đường link."""

import re

_ID = r"[A-Za-z0-9_-]{20,}"
_FROM_LINK = re.compile(rf"/spreadsheets/d/({_ID})")
_BARE_ID = re.compile(rf"^{_ID}$")


class InvalidSpreadsheetError(ValueError):
    pass


def parse_spreadsheet_id(text: str) -> str:
    cleaned = text.strip()
    if match := _FROM_LINK.search(cleaned):
        return match.group(1)
    if _BARE_ID.match(cleaned):
        return cleaned
    raise InvalidSpreadsheetError(text)

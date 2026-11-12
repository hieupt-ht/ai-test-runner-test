import pytest

from app.core.sheets.spreadsheet_id import InvalidSpreadsheetError, parse_spreadsheet_id

SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"


@pytest.mark.parametrize(
    "text",
    [
        SHEET_ID,
        f"  https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=0 ",
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}",
    ],
)
def test_parse_spreadsheet_id(text: str) -> None:
    assert parse_spreadsheet_id(text) == SHEET_ID


@pytest.mark.parametrize("text", ["", "abc", "https://example.com/x"])
def test_parse_spreadsheet_id_rejects(text: str) -> None:
    with pytest.raises(InvalidSpreadsheetError):
        parse_spreadsheet_id(text)

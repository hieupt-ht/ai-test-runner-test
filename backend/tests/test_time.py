from datetime import UTC

from app.core.time import from_iso


def test_from_iso_thieu_mui_gio_coi_la_utc():
    # Sheet bị sửa tay, mất chữ Z: vẫn phải có múi giờ để so sánh với giờ khác không bị lỗi
    parsed = from_iso("2026-11-19T10:00:00")
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == UTC.utcoffset(None)


def test_from_iso_giu_nguyen_mui_gio_da_co():
    assert from_iso("2026-11-19T10:00:00+07:00").utcoffset().total_seconds() == 7 * 3600
    assert from_iso("2026-11-19T10:00:00Z").utcoffset().total_seconds() == 0

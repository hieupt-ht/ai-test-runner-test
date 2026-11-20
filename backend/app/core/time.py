from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(moment: datetime) -> str:
    """Định dạng thời gian lưu trên Sheet, ví dụ `2026-11-12T08:30:00Z` (giờ UTC)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(text: str) -> datetime:
    parsed = datetime.fromisoformat(text)
    # Sheet bị sửa tay có thể mất chữ Z: coi là UTC để so sánh với giờ khác không bị lỗi
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


def today_in_vietnam() -> date:
    """Ngày hôm nay theo giờ Việt Nam (dùng để so deadline)."""
    return datetime.now(VIETNAM).date()

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel
from redis import Redis

from app.core.models.user import normalize_email


class Notification(BaseModel):
    id: str
    type: str
    title: str
    link: str
    created_at: str
    read: bool = False


class NotificationStore:
    def __init__(
        self,
        redis: Redis,
        *,
        max_items: int = 100,
        ttl_seconds: int = 30 * 24 * 3600,
    ) -> None:
        self.redis = redis
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds

    def _key(self, email: str) -> str:
        return f"notifications:{normalize_email(email)}"

    def add(self, email: str, *, type: str, title: str, link: str) -> None:
        item = Notification(
            id=str(uuid4()),
            type=type,
            title=title,
            link=link,
            created_at=datetime.now(UTC).isoformat(),
        )
        key = self._key(email)
        self.redis.lpush(key, item.model_dump_json())
        self.redis.ltrim(key, 0, self.max_items - 1)
        self.redis.expire(key, self.ttl_seconds)

    def list(self, email: str) -> list[Notification]:
        values = self.redis.lrange(self._key(email), 0, -1)
        return [Notification.model_validate_json(value) for value in values]

    def unread_count(self, email: str) -> int:
        return sum(not item.read for item in self.list(email))

    def mark_read(self, email: str, notification_id: str) -> bool:
        key = self._key(email)
        items = self.list(email)
        found = False
        updated: list[str] = []
        for item in items:
            if item.id == notification_id:
                item = item.model_copy(update={"read": True})
                found = True
            updated.append(item.model_dump_json())
        if found:
            self._replace(key, updated)
        return found

    def mark_all_read(self, email: str) -> None:
        key = self._key(email)
        updated = [
            item.model_copy(update={"read": True}).model_dump_json()
            for item in self.list(email)
        ]
        self._replace(key, updated)

    def _replace(self, key: str, items: builtins.list[str]) -> None:
        pipe = self.redis.pipeline()
        pipe.delete(key)
        if items:
            pipe.rpush(key, *items)
        pipe.expire(key, self.ttl_seconds)
        pipe.execute()


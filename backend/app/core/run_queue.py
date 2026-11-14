"""Hàng đợi run, cờ huỷ và ghi chú lý do lỗi, đều nằm trong Redis.

Redis bật AOF nên job không mất khi khởi động lại. Cờ huỷ và ghi chú tự hết hạn sau 30 ngày.
"""

from pydantic import BaseModel
from redis import Redis

QUEUE_KEY = "queue:runs"
EXPIRE_SECONDS = 30 * 24 * 60 * 60


class RunJob(BaseModel):
    project_id: str
    run_id: str
    case_ids: list[str]


# Mã run (RUN-0001) được đánh số theo TỪNG dự án nên lặp lại ở mọi dự án: khoá phải kèm mã dự án.
def _cancel_key(project_id: str, run_id: str) -> str:
    return f"run:{project_id}:{run_id}:cancel"


def _note_key(project_id: str, run_id: str) -> str:
    return f"run:{project_id}:{run_id}:note"


class RunQueue:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def push(self, job: RunJob) -> None:
        self._redis.rpush(QUEUE_KEY, job.model_dump_json())

    def pop(self, timeout_seconds: int) -> RunJob | None:
        """Chờ tối đa `timeout_seconds` giây lấy job đầu hàng; không có thì trả None."""
        item = self._redis.blpop([QUEUE_KEY], timeout=timeout_seconds)
        if item is None:
            return None
        _key, payload = item
        return RunJob.model_validate_json(payload)

    def request_cancel(self, project_id: str, run_id: str) -> None:
        self._redis.set(_cancel_key(project_id, run_id), "1", ex=EXPIRE_SECONDS)

    def is_cancelled(self, project_id: str, run_id: str) -> bool:
        return bool(self._redis.exists(_cancel_key(project_id, run_id)))

    def set_note(self, project_id: str, run_id: str, text: str) -> None:
        self._redis.set(_note_key(project_id, run_id), text, ex=EXPIRE_SECONDS)

    def get_note(self, project_id: str, run_id: str) -> str:
        value = self._redis.get(_note_key(project_id, run_id))
        if value is None:
            return ""
        return value.decode() if isinstance(value, bytes) else str(value)

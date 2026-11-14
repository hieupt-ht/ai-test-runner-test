"""Tiến trình worker: `uv run python -m app.worker`.

Chạy thẳng trên máy có app cần test (không Docker). Lấy job từ Redis, chạy từng run một.
"""

import logging
import sys

from app.api.services import build_gateway, build_services, is_configured
from app.core.run_queue import RunQueue
from app.settings import get_settings
from app.worker.run_executor import RunExecutor, real_session_opener

logger = logging.getLogger("app.worker")
POLL_SECONDS = 5


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    if not is_configured(settings):
        logger.error("Chưa cấu hình GOOGLE_SERVICE_ACCOUNT_JSON / SYSTEM_SPREADSHEET_ID trong .env")
        return 1

    # Worker không cache danh sách case: phải thấy đúng case nào đang APPROVED lúc chạy.
    uncached = settings.model_copy(update={"sheet_cache_ttl_seconds": 0})
    services = build_services(uncached, build_gateway(uncached))
    queue = RunQueue(services.redis)
    executor = RunExecutor(services, uncached, queue, real_session_opener(uncached))

    fixed = executor.recover_interrupted_runs()
    if fixed:
        logger.warning("Đã đánh dấu %d run dở dang là FAILED", fixed)

    logger.info("Worker sẵn sàng, đang chờ job (Ctrl+C để dừng)")
    try:
        while True:
            job = queue.pop(timeout_seconds=POLL_SECONDS)
            if job is None:
                continue
            logger.info("Nhận run %s (%d case)", job.run_id, len(job.case_ids))
            try:
                executor.execute(job)
            except Exception:
                logger.exception("Run %s gặp lỗi", job.run_id)
    except KeyboardInterrupt:
        logger.info("Worker dừng")
    return 0


if __name__ == "__main__":
    sys.exit(main())

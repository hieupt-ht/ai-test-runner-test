"""Dọn bằng chứng cũ: mỗi case chỉ giữ ảnh/video của 5 lần chạy gần nhất."""

import logging
from typing import Protocol

from app.core.models.media import Media
from app.core.models.run import Result

logger = logging.getLogger(__name__)

KEEP_RESULTS = 5


class ResultStore(Protocol):
    def list_all(self) -> list[Result]: ...
    def mark_pruned(self, result_ids: list[str]) -> None: ...


class MediaDeleter(Protocol):
    def delete(self, items: list[Media]) -> None: ...


def result_media(result: Result) -> list[Media]:
    """Mọi file của mình trong một kết quả: video, ảnh chụp và ảnh từng bước."""
    items: list[Media] = []
    if result.evidence.video is not None:
        items.append(result.evidence.video)
    items.extend(result.evidence.screenshots)
    items.extend(step.screenshot for step in result.step_results if step.screenshot is not None)
    return items


def results_to_prune(results: list[Result], case_ids: set[str]) -> list[Result]:
    """Với mỗi case: bỏ 5 kết quả mới nhất, trả các kết quả cũ hơn còn giữ file."""
    chosen: list[Result] = []
    for case_id in case_ids:
        of_case = sorted(
            (r for r in results if r.test_case_id == case_id),
            key=lambda r: (r.created_at, r.run_id),
            reverse=True,
        )
        for old in of_case[KEEP_RESULTS:]:
            # Link cũ (legacy_url) không phải file của mình nên không xoá được
            if not old.evidence.pruned and result_media(old):
                chosen.append(old)
    return chosen


def prune_evidence(
    results_repo: ResultStore, janitor: MediaDeleter | None, case_ids: set[str]
) -> None:
    """Xoá file cũ rồi đánh dấu `pruned`. Lỗi chỉ ghi log để không làm hỏng việc ghi kết quả."""
    if janitor is None:
        return
    try:
        old = results_to_prune(results_repo.list_all(), case_ids)
        if not old:
            return
        for result in old:
            janitor.delete(result_media(result))
        results_repo.mark_pruned([result.id for result in old])
    except Exception:
        logger.warning("Không dọn được bằng chứng cũ", exc_info=True)

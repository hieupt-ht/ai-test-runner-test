"""Gửi tín hiệu "chạy lại" lên GitHub issue của case.

App không gọi được Codex, nên chỉ để lại dấu vết trên issue để người mở Codex thấy.
"""

import logging
from datetime import datetime

from app.core.github.client import GitHubClient
from app.core.github.issue_format import case_label
from app.core.services.result_issue_sync import FAIL_LABEL, PASS_LABEL, RERUN_LABEL
from app.core.time import VIETNAM

logger = logging.getLogger(__name__)

RERUN_MARKER = "<!-- ai-test-runner-rerun -->"
RERUN_LABEL_COLOR = "e6a817"


def format_rerun_comment(
    user_name: str, requested_at: datetime, *, run_id: str | None = None
) -> str:
    # Ghi giờ Việt Nam cho người dùng dễ đọc
    local_time = requested_at.astimezone(VIETNAM)
    lines = [
        RERUN_MARKER,
        f"🔄 **Yêu cầu chạy lại** — {user_name} · {local_time:%Y-%m-%d %H:%M}",
        "Mở Codex và chạy lại case này.",
    ]
    if run_id:
        # Chạy bộ regression: Codex phải gửi kèm mã này để kết quả vào đúng lần chạy
        lines.append(f'Mã lần chạy: {run_id} — gửi kèm "run_id" khi báo kết quả.')
    return "\n".join(lines)


def request_rerun_on_issue(
    github: GitHubClient,
    *,
    repo: str,
    case_id: str,
    user_name: str,
    requested_at: datetime,
    run_id: str | None = None,
) -> None:
    """Comment + mở lại issue + gắn nhãn needs-rerun. Mỗi việc lỗi riêng chỉ ghi log."""
    try:
        issue = github.find_issue_by_label(repo, case_label(case_id))
    except Exception as error:  # noqa: BLE001 - lỗi GitHub không được làm hỏng yêu cầu
        logger.warning("Không tìm được issue của %s để yêu cầu chạy lại: %s", case_id, error)
        return
    if issue is None:
        logger.warning("Case %s chưa có issue trên GitHub, bỏ qua yêu cầu chạy lại", case_id)
        return

    try:
        body = format_rerun_comment(user_name, requested_at, run_id=run_id)
        github.create_issue_comment(repo, issue.number, body)
    except Exception as error:  # noqa: BLE001
        logger.warning("Không comment được yêu cầu chạy lại cho %s: %s", case_id, error)

    # Việc 2 và 3 cùng gọi một API cập nhật issue nên gộp thành một lần gọi,
    # nhưng vẫn tách try/except để lỗi nhãn không chặn việc mở lại issue.
    labels = [label for label in issue.labels if label not in (PASS_LABEL, FAIL_LABEL)]
    try:
        github.ensure_label(repo, RERUN_LABEL, color=RERUN_LABEL_COLOR)
        if RERUN_LABEL not in labels:
            labels.append(RERUN_LABEL)
    except Exception as error:  # noqa: BLE001
        logger.warning("Không tạo được nhãn %s cho %s: %s", RERUN_LABEL, case_id, error)
        labels = list(issue.labels)  # không gắn nhãn mới, giữ nguyên nhãn cũ
    try:
        github.update_issue_state_and_labels(repo, issue.number, state="open", labels=labels)
    except Exception as error:  # noqa: BLE001
        logger.warning("Không mở lại/gắn nhãn issue của %s: %s", case_id, error)

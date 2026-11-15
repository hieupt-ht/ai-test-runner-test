"""Cập nhật comment kết quả và trạng thái issue sau khi đã ghi kết quả vào app."""

import re
from typing import Literal
from urllib.parse import urlparse

from app.core.github.client import GitHubClient, IssueInfo
from app.core.github.issue_format import case_label
from app.core.models.run import Result, ResultStatus, Run
from app.core.models.test_case import TestCase

RESULT_MARKER = "<!-- ai-test-runner-result -->"
PASS_LABEL = "test: pass"
FAIL_LABEL = "test: fail"
RERUN_LABEL = "needs-rerun"  # có kết quả mới thì yêu cầu chạy lại đã được đáp ứng


def _private_values(case: TestCase) -> list[str]:
    values = [case.test_data, case.created_by]
    for part in re.split(r"[,;\n&{}\"]+", case.test_data):
        if "=" in part:
            values.append(part.split("=", 1)[1].strip().strip("'\""))
        elif ":" in part:
            values.append(part.split(":", 1)[1].strip().strip("'\""))
    return sorted({value for value in values if len(value) >= 3}, key=len, reverse=True)


def _safe_text(value: str, case: TestCase) -> str:
    safe = value
    for secret in _private_values(case):
        safe = re.sub(re.escape(secret), "[đã ẩn]", safe, flags=re.IGNORECASE)
    safe = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[đã ẩn email]", safe)
    safe = re.sub(
        r"(?i)(password|passwd|mật khẩu|token|api[_ -]?key)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2[đã ẩn]",
        safe,
    )
    safe = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [đã ẩn]", safe)
    return safe.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _safe_evidence(value: str | None, case: TestCase) -> str | None:
    if not value or not value.startswith("https://"):
        return None
    if re.search(
        r"(?i)[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(password|passwd|token|api[_-]?key)=",
        value,
    ):
        return None
    if any(secret.casefold() in value.casefold() for secret in _private_values(case)):
        return None
    return value if urlparse(value).scheme == "https" else None


def format_pass_comment(
    run: Run,
    result: Result,
    case: TestCase,
    *,
    app_url: str,
    project_id: str,
    duration: float = 0,
) -> str:
    step_count = len(case.steps)
    finished = run.finished_at.isoformat() if run.finished_at else "Chưa hoàn tất"
    return "\n".join(
        [
            RESULT_MARKER,
            f"## Kết quả test · ✅ PASS · {case.id}",
            "",
            f"**Lần chạy:** #{run.id} · {finished}",
            f"**Thời gian:** {duration:g}s · **Số bước:** {step_count}/{step_count}",
            "",
            f"[Xem chi tiết trong app →]({app_url.rstrip('/')}/projects/{project_id}/results)",
        ]
    )


def format_fail_comment(
    run: Run,
    result: Result,
    case: TestCase,
    *,
    app_url: str,
    project_id: str,
    duration: float = 0,
) -> str:
    failed_step = result.failed_step or 0
    lines = [
        RESULT_MARKER,
        f"## Kết quả test · ❌ FAIL · {case.id}",
        "",
        (
            f"**Lần chạy:** #{run.id} · "
            f"{run.finished_at.isoformat() if run.finished_at else ''} · "
            f"**Bước lỗi:** {failed_step}/{len(case.steps)}"
        ),
        f"**Thời gian:** {duration:g}s",
        "",
        "| Bước | Mô tả | Kết quả |",
        "|------|-------|---------|",
    ]
    for number, step in enumerate(case.steps, start=1):
        status = "✅" if number < failed_step else "❌" if number == failed_step else "—"
        lines.append(f"| {number} | {_safe_text(step.action, case)} | {status} |")
    lines.extend(["", f"**Lý do:** {_safe_text(result.reason, case)}"])
    evidence = _safe_evidence(result.screenshot, case)
    if evidence:
        lines.append(f"**Bằng chứng:** [Mở bằng chứng]({evidence})")
    lines.extend(
        [
            "",
            f"[Xem chi tiết trong app →]({app_url.rstrip('/')}/projects/{project_id}/results)",
        ]
    )
    return "\n".join(lines)


def find_bot_comment(github: GitHubClient, repo: str, issue_number: int) -> int | None:
    comments = github.list_issue_comments(repo, issue_number)
    existing = next((comment for comment in comments if RESULT_MARKER in comment.body), None)
    return existing.id if existing else None


def upsert_result_comment(github: GitHubClient, repo: str, issue_number: int, body: str) -> None:
    comment_id = find_bot_comment(github, repo, issue_number)
    if comment_id is not None:
        github.update_issue_comment(repo, comment_id, body)
    else:
        github.create_issue_comment(repo, issue_number, body)


def sync_issue_state(
    github: GitHubClient,
    repo: str,
    issue: IssueInfo,
    passed: bool,
) -> None:
    state: Literal["open", "closed"] = "closed" if passed else "open"
    add_label, remove_label = (PASS_LABEL, FAIL_LABEL) if passed else (FAIL_LABEL, PASS_LABEL)
    github.ensure_label(repo, add_label, color="2da44e" if passed else "d73a4a")
    labels = [label for label in issue.labels if label not in (remove_label, RERUN_LABEL)]
    if add_label not in labels:
        labels.append(add_label)
    github.update_issue_state_and_labels(repo, issue.number, state=state, labels=labels)


def sync_result_issue(
    github: GitHubClient,
    *,
    repo: str,
    project_id: str,
    app_url: str,
    run: Run,
    result: Result,
    case: TestCase,
    duration: float = 0,
) -> None:
    if result.status not in (ResultStatus.PASS, ResultStatus.FAIL):
        return
    issue = github.find_issue_by_label(repo, case_label(case.id))
    if issue is None:
        return
    if result.status == ResultStatus.PASS:
        body = format_pass_comment(
            run,
            result,
            case,
            app_url=app_url,
            project_id=project_id,
            duration=duration,
        )
    else:
        body = format_fail_comment(
            run,
            result,
            case,
            app_url=app_url,
            project_id=project_id,
            duration=duration,
        )
    upsert_result_comment(github, repo, issue.number, body)
    sync_issue_state(github, repo, issue, result.status == ResultStatus.PASS)

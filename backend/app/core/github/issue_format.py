"""Soạn bản sao công khai của test case cho GitHub issue."""

from dataclasses import dataclass

from app.core.models.test_case import TestCase, TestCaseStatus

ISSUE_LABEL = "test-case"
MAX_BODY_LENGTH = 65536
TRUNCATION_NOTE = "\n\n_Nội dung quá dài, đã được cắt bớt._"


@dataclass(frozen=True)
class IssueContent:
    title: str
    body: str
    labels: list[str]


def case_label(case_id: str) -> str:
    return f"tc:{case_id}"


def status_label(status: TestCaseStatus) -> str:
    return f"status:{status.value}"


def _safe_text(value: str) -> str:
    """Chặn nhắc tên GitHub và ký tự mở cú pháp Markdown trong chữ tự do."""
    return (
        value.replace("@", "@\u200b")
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("*", "\\*")
        .replace("[", "\\[")
        .replace("#", "\\#")
    )


def render_issue(case: TestCase, *, screen_name: str = "") -> IssueContent:
    lines = [
        f"<!-- {case_label(case.id)} v{case.version} -->",
        f"# [{case.id}] {_safe_text(case.title)}",
        "",
        f"- Màn hình: {_safe_text(screen_name or case.screen_id)}",
        f"- Mức độ: {case.severity.value}",
        f"- Ưu tiên: {case.priority.value}",
        f"- Trạng thái: {case.status.value}",
        "",
        "## Điều kiện tiên quyết",
        _safe_text(case.precondition),
        "",
        "## Các bước",
    ]
    for number, step in enumerate(case.steps, start=1):
        lines.append(f"{number}. {_safe_text(step.action)}")
        if step.expected:
            lines.append(f"   - Kết quả mong đợi: {_safe_text(step.expected)}")
    lines.extend(["", "## Kết quả mong đợi", _safe_text(case.expected_result)])
    body = "\n".join(lines)
    if len(body) > MAX_BODY_LENGTH:
        body = body[: MAX_BODY_LENGTH - len(TRUNCATION_NOTE)] + TRUNCATION_NOTE
    return IssueContent(
        title=f"[{case.id}] {case.title}",
        body=body,
        labels=[ISSUE_LABEL, case_label(case.id), status_label(case.status)],
    )

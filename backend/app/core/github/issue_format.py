"""Soạn bản sao công khai của test case cho GitHub issue."""

from dataclasses import dataclass

from app.core.media.frames import video_frame_urls
from app.core.models.media import Media, MediaKind, display_url, thumbnail_url
from app.core.models.project import Project
from app.core.models.screen import Screen
from app.core.models.test_case import Platform, TestCase, TestCaseStatus

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


def platform_label(platform: Platform) -> str:
    return f"platform: {platform.value.lower()}"


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


def _media_lines(items: list[Media], indent: str) -> list[str]:
    """Ảnh hiện thẳng trong issue; video để link và vài ảnh cắt cho Codex xem."""
    lines: list[str] = []
    for item in items:
        if item.kind == MediaKind.IMAGE:
            lines.append(f"{indent}![{_safe_text(item.note)}]({display_url(item)})")
        else:
            lines.append(f"{indent}Video: {item.url}")
            frames = video_frame_urls(item)
            if frames:
                lines.append(f"{indent}Ảnh cắt: {' '.join(frames)}")
            elif (cover := thumbnail_url(item)) is not None:
                lines.append(f"{indent}Ảnh đại diện: {cover}")
            if item.note:
                lines.append(f"{indent}Ghi chú video: {_safe_text(item.note)}")
    return lines


def _app_id_lines(case: TestCase, project: Project | None) -> list[str]:
    """Mã app chỉ có ý nghĩa với đúng nền tảng của case."""
    if project is None:
        return []
    if case.platform == Platform.ANDROID and project.android_app_id:
        return [f"- android_app_id: {_safe_text(project.android_app_id)}", ""]
    if case.platform == Platform.IOS and project.ios_bundle_id:
        return [f"- ios_bundle_id: {_safe_text(project.ios_bundle_id)}", ""]
    return []


def render_issue(
    case: TestCase,
    *,
    project: Project | None = None,
    screen: Screen | None = None,
    screen_name: str = "",
    project_id: str = "",
    app_base_url: str = "",
) -> IssueContent:
    shown_screen = screen_name or (screen.name if screen else "") or case.screen_id
    lines = [
        f"<!-- {case_label(case.id)} v{case.version} -->",
        f"# [{case.id}] {_safe_text(case.title)}",
    ]
    if project_id and app_base_url:
        endpoint = (
            f"{app_base_url.rstrip('/')}/api/agent/projects/{project_id}/results"
        )
        lines.extend(
            [
                "",
                "## Báo cáo cho AI Test Runner",
                f"- Mã dự án: `{_safe_text(project_id)}`",
                f"- Endpoint: `{_safe_text(endpoint)}`",
                "- Xác thực: `Authorization: Bearer` từ biến môi trường `AGENT_API_TOKEN`",
            ]
        )
    lines.extend(
        [
            "",
            f"- Phiên bản case: v{case.version}",
            f"- Màn hình: {_safe_text(shown_screen)}",
            f"- Nền tảng: {case.platform.value}",
            f"- Loại test: {case.test_type.value}",
            f"- Regression: {'có' if case.regression else 'không'}",
            f"- Điểm bắt đầu: {_safe_text(case.start_point or (screen.route if screen else ''))}",
            f"- Mức độ: {case.severity.value}",
            f"- Ưu tiên: {case.priority.value}",
            f"- Trạng thái: {case.status.value}",
            "",
            *_app_id_lines(case, project),
            "## Điều kiện tiên quyết",
            _safe_text(case.precondition),
            "",
            "## Các bước",
        ]
    )
    for number, step in enumerate(case.steps, start=1):
        lines.append(f"{number}. {_safe_text(step.action)}")
        if step.expected:
            lines.append(f"   - Kết quả mong đợi: {_safe_text(step.expected)}")
        lines.extend(_media_lines(step.guide_media, "   "))
    lines.extend(["", "## Kết quả mong đợi", _safe_text(case.expected_result)])
    if case.guide_media:
        lines.extend(["", "## Ảnh/video cho cả case", *_media_lines(case.guide_media, "")])
    body = "\n".join(lines)
    if len(body) > MAX_BODY_LENGTH:
        body = body[: MAX_BODY_LENGTH - len(TRUNCATION_NOTE)] + TRUNCATION_NOTE
    return IssueContent(
        title=f"[{case.id}] {case.title}",
        body=body,
        labels=[
            ISSUE_LABEL,
            case_label(case.id),
            status_label(case.status),
            platform_label(case.platform),
        ],
    )

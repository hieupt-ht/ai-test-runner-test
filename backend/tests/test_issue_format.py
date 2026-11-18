"""Nội dung issue phải dễ đọc và không lộ dữ liệu riêng."""

from datetime import UTC, datetime

from app.core.github.issue_format import render_issue
from app.core.models.media import Media
from app.core.models.project import Project
from app.core.models.screen import Screen
from app.core.models.test_case import (
    Platform,
    Priority,
    Severity,
    TestCase,
    TestCaseStatus,
    TestStep,
    TestType,
)


def make_case(**changes: object) -> TestCase:
    data: dict[str, object] = {
        "id": "TC-000123",
        "screen_id": "SCR-001",
        "title": "Đăng nhập",
        "precondition": "Đã mở trang",
        "test_data": "matkhau123",
        "steps": [TestStep(action="Nhập email", expected="Hiện thông báo")],
        "expected_result": "Vào trang chính",
        "severity": Severity.HIGH,
        "priority": Priority.P1,
        "status": TestCaseStatus.APPROVED,
        "created_by": "an@x.com",
        "updated_by": "binh@x.com",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "version": 3,
    }
    data.update(changes)
    return TestCase.model_validate(data)


def test_title_has_case_id_prefix() -> None:
    assert render_issue(make_case()).title == "[TC-000123] Đăng nhập"


def test_labels_are_test_case_case_id_status_and_platform() -> None:
    assert render_issue(make_case()).labels == [
        "test-case",
        "tc:TC-000123",
        "status:APPROVED",
        "platform: web",
    ]


def test_body_lists_steps_with_expected_and_expected_result() -> None:
    body = render_issue(make_case(), screen_name="Màn đăng nhập").body
    assert "Màn đăng nhập" in body
    assert "1. Nhập email" in body
    assert "Kết quả mong đợi: Hiện thông báo" in body
    assert "Vào trang chính" in body


def test_body_never_contains_test_data() -> None:
    assert "matkhau123" not in render_issue(make_case()).body


def test_body_never_contains_creator_emails() -> None:
    body = render_issue(make_case()).body
    assert "an@x.com" not in body
    assert "binh@x.com" not in body


def test_body_with_vietnamese_and_markdown_special_chars_is_kept_readable() -> None:
    case = make_case(title="Lỗi | `mã` #1", steps=[TestStep(action="Bấm @admin", expected="OK")])
    body = render_issue(case).body
    assert "Lỗi | \\`mã\\` \\#1" in body
    assert "@admin" not in body
    assert "Bấm" in body


def test_body_has_marker_with_case_id_and_version() -> None:
    assert "<!-- tc:TC-000123 v3 -->" in render_issue(make_case()).body


def test_body_has_project_and_endpoint_for_agent_to_report_result() -> None:
    body = render_issue(
        make_case(),
        project_id="PRJ-0001",
        app_base_url="http://localhost:3000/",
    ).body
    assert "Mã dự án: `PRJ-0001`" in body
    assert (
        "Endpoint: `http://localhost:3000/api/agent/projects/PRJ-0001/results`" in body
    )
    assert "AGENT_API_TOKEN" in body


def test_very_long_case_body_is_truncated_under_github_limit() -> None:
    case = make_case().model_copy(update={"precondition": "a" * 70000})
    body = render_issue(case).body
    assert len(body) <= 65536
    assert "đã được cắt bớt" in body


def make_project(**changes: object) -> Project:
    data: dict[str, object] = {
        "id": "PRJ-0001",
        "name": "Dự án",
        "repo_full_name": "org/web",
        "branch": "main",
        "staging_url": "",
        "spreadsheet_id": "sheet-1",
        "archived": False,
        "created_at": datetime.now(UTC),
        "android_app_id": "com.shop.app",
        "ios_bundle_id": "vn.shop.app",
    }
    data.update(changes)
    return Project.model_validate(data)


def make_screen(route: str = "/login") -> Screen:
    return Screen(
        id="SCR-001",
        name="Đăng nhập",
        description="",
        route=route,
        code_paths=[],
        created_at=datetime.now(UTC),
    )


CLOUD = "https://res.cloudinary.com/demo"


def image(note: str = "", name: str = "a") -> Media:
    return Media(
        kind="image", url=f"{CLOUD}/image/upload/v1/ai/{name}.png", public_id=name, note=note
    )


def video(name: str = "v") -> Media:
    return Media(kind="video", url=f"{CLOUD}/video/upload/v1/ai/{name}.mp4", public_id=name)


def test_body_has_case_version_for_codex_to_send_back() -> None:
    assert "- Phiên bản case: v3" in render_issue(make_case()).body


def test_body_has_platform_type_regression_and_start_point() -> None:
    case = make_case(
        platform=Platform.WEB, test_type=TestType.UI, regression=True, start_point="/cart"
    )
    body = render_issue(case, project=make_project(), screen=make_screen()).body
    assert "- Nền tảng: WEB" in body
    assert "- Loại test: UI" in body
    assert "- Regression: có" in body
    assert "- Điểm bắt đầu: /cart" in body


def test_empty_start_point_falls_back_to_screen_route() -> None:
    body = render_issue(make_case(), screen=make_screen("/login")).body
    assert "- Điểm bắt đầu: /login" in body
    assert "- Regression: không" in body


def test_android_case_has_android_app_id_and_no_ios_id() -> None:
    body = render_issue(make_case(platform=Platform.ANDROID), project=make_project()).body
    assert "android_app_id: com.shop.app" in body
    assert "vn.shop.app" not in body


def test_ios_case_has_bundle_id_and_no_android_id() -> None:
    body = render_issue(make_case(platform=Platform.IOS), project=make_project()).body
    assert "ios_bundle_id: vn.shop.app" in body
    assert "com.shop.app" not in body


def test_web_case_has_no_app_ids() -> None:
    body = render_issue(make_case(), project=make_project()).body
    assert "com.shop.app" not in body
    assert "vn.shop.app" not in body


def test_platform_label_follows_platform() -> None:
    labels = render_issue(make_case(platform=Platform.ANDROID)).labels
    assert "platform: android" in labels


def test_step_image_is_listed_under_its_step() -> None:
    step = TestStep(action="Bấm nút", expected="", guide_media=[image("nút Đăng nhập")])
    body = render_issue(make_case(steps=[step])).body
    assert f"![nút Đăng nhập]({CLOUD}/image/upload/v1/ai/a.png)" in body


def test_step_video_lists_url_and_frames() -> None:
    step = TestStep(action="Vuốt", expected="", guide_media=[video()])
    body = render_issue(make_case(steps=[step])).body
    assert f"Video: {CLOUD}/video/upload/v1/ai/v.mp4" in body
    assert f"Ảnh cắt: {CLOUD}/video/upload/so_1/v1/ai/v.jpg" in body
    assert "so_11/" in body


def test_case_level_media_has_its_own_section() -> None:
    body = render_issue(make_case(guide_media=[image("tổng quan")])).body
    assert "## Ảnh/video cho cả case" in body
    assert f"![tổng quan]({CLOUD}/image/upload/v1/ai/a.png)" in body


def test_no_case_media_section_when_empty() -> None:
    assert "## Ảnh/video cho cả case" not in render_issue(make_case()).body


def test_media_note_with_email_or_mention_is_neutralised() -> None:
    step = TestStep(action="Bấm", expected="", guide_media=[image("gửi @admin")])
    body = render_issue(make_case(steps=[step])).body
    assert "@admin" not in body
    assert "@​admin" in body


def drive_image(note: str = "") -> Media:
    return Media(
        kind="image", url="https://drive.google.com/file/d/img1/view", public_id="img1", note=note
    )


def drive_video() -> Media:
    return Media(kind="video", url="https://drive.google.com/file/d/vid1/view", public_id="vid1")


def test_drive_image_in_issue_uses_thumbnail_link() -> None:
    step = TestStep(action="Bấm", expected="", guide_media=[drive_image("nút")])
    body = render_issue(make_case(steps=[step])).body
    assert "![nút](https://drive.google.com/thumbnail?id=img1&sz=w1600)" in body


def test_drive_video_in_issue_has_link_and_cover_but_no_cut_frames() -> None:
    step = TestStep(action="Vuốt", expected="", guide_media=[drive_video()])
    body = render_issue(make_case(steps=[step])).body
    assert "Video: https://drive.google.com/file/d/vid1/view" in body
    assert "Ảnh đại diện: https://drive.google.com/thumbnail?id=vid1&sz=w1600" in body
    assert "Ảnh cắt" not in body

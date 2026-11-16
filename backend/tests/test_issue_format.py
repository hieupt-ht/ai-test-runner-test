"""Nội dung issue phải dễ đọc và không lộ dữ liệu riêng."""

from datetime import UTC, datetime

from app.core.github.issue_format import render_issue
from app.core.models.test_case import Priority, Severity, TestCase, TestCaseStatus, TestStep


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


def test_labels_are_test_case_case_id_and_status() -> None:
    assert render_issue(make_case()).labels == ["test-case", "tc:TC-000123", "status:APPROVED"]


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

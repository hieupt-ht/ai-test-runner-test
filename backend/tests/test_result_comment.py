"""Comment kết quả trên issue: bảng từng bước, ảnh lỗi, video, môi trường."""

from datetime import UTC, datetime

from app.core.models.media import Media
from app.core.models.run import Evidence, Result, ResultStatus, Run, RunScope, RunStatus, StepResult
from app.core.models.test_case import Priority, Severity, TestCase, TestCaseStatus, TestStep
from app.core.services.result_issue_sync import format_fail_comment, format_pass_comment

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def media(name: str, kind: str = "image") -> Media:
    return Media(
        kind=kind, url=f"https://res.cloudinary.com/m/{kind}/upload/{name}.png", public_id=name
    )


def make_case() -> TestCase:
    return TestCase(
        id="TC-1", screen_id="S", title="t", precondition="", test_data="",
        steps=[TestStep(action=f"Bước {n}", expected="ok") for n in (1, 2, 3)],
        expected_result="ok", severity=Severity.HIGH, priority=Priority.P1,
        status=TestCaseStatus.APPROVED, created_by="an@x.com", updated_by="an@x.com",
        created_at=NOW, updated_at=NOW, version=2,
    )


def make_run() -> Run:
    return Run(
        id="RUN-0001", triggered_by="codex", scope=RunScope(), branch="main", commit_sha="",
        status=RunStatus.COMPLETED, started_at=NOW, finished_at=NOW, total=1, passed=0,
        failed=1, tokens_used=0,
    )


def make_result(status: ResultStatus = ResultStatus.FAIL, **changes: object) -> Result:
    data: dict[str, object] = {
        "id": "RUN-0001-TC-1", "run_id": "RUN-0001", "test_case_id": "TC-1", "status": status,
        "reason": "Lỗi", "failed_step": 2, "created_at": NOW,
    }
    data.update(changes)
    return Result.model_validate(data)


def fail_comment(result: Result) -> str:
    return format_fail_comment(
        make_run(), result, make_case(), app_url="http://app", project_id="PRJ-1"
    )


def test_step_table_has_pass_fail_skipped_in_order() -> None:
    steps = [
        StepResult(step_no=1, status="PASS", actual="ok"),
        StepResult(step_no=2, status="FAIL", actual="Hiện lỗi"),
        StepResult(step_no=3, status="SKIPPED"),
    ]
    body = fail_comment(make_result(step_results=steps))
    rows = [line for line in body.splitlines() if line[:4] in ("| 1 ", "| 2 ", "| 3 ")]
    assert [("✅" in r, "❌" in r, "–" in r) for r in rows] == [
        (True, False, False), (False, True, False), (False, False, True),
    ]
    assert "Thực tế" in body and "Hiện lỗi" in body


def test_missing_step_result_shows_dash() -> None:
    body = fail_comment(make_result(step_results=[StepResult(step_no=1, status="PASS")]))
    assert "| 3 | Bước 3 | – |" in body


def test_without_step_results_falls_back_to_failed_step() -> None:
    body = fail_comment(make_result())
    assert "| 1 | Bước 1 | ✅ |" in body
    assert "| 2 | Bước 2 | ❌ |" in body
    assert "| 3 | Bước 3 | — |" in body


def test_failed_step_screenshot_video_environment_and_version() -> None:
    result = make_result(
        step_results=[StepResult(step_no=2, status="FAIL", screenshot=media("err"))],
        evidence=Evidence(video=media("vid", "video")),
        environment="Pixel 7 / Android 14",
        case_version=2,
    )
    body = fail_comment(result)
    assert "**Ảnh bước lỗi:** [Mở ảnh](https://res.cloudinary.com/m/image/upload/err.png)" in body
    assert "**Video:** [Xem video](https://res.cloudinary.com/m/video/upload/vid.png)" in body
    assert "**Môi trường:** Pixel 7 / Android 14" in body
    assert "**Chạy với:** v2" in body


def test_actual_text_with_email_is_hidden() -> None:
    steps = [StepResult(step_no=2, status="FAIL", actual="gửi cho bob@x.com")]
    body = fail_comment(make_result(step_results=steps))
    assert "bob@x.com" not in body
    assert "[đã ẩn email]" in body


def test_pass_comment_has_table_and_extras_when_steps_known() -> None:
    steps = [StepResult(step_no=n, status="PASS", actual="ok") for n in (1, 2, 3)]
    result = make_result(
        ResultStatus.PASS, step_results=steps, environment="Chrome", case_version=2
    )
    body = format_pass_comment(
        make_run(), result, make_case(), app_url="http://app", project_id="PRJ-1"
    )
    assert body.count("✅") >= 4
    assert "**Môi trường:** Chrome" in body
    assert "**Chạy với:** v2" in body


def test_pass_comment_without_steps_is_unchanged_shape() -> None:
    body = format_pass_comment(
        make_run(), make_result(ResultStatus.PASS), make_case(), app_url="http://app",
        project_id="PRJ-1",
    )
    assert "| Bước |" not in body

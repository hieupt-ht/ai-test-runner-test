"""Chạy MỘT test case bằng Playwright và quyết định PASS / FAIL / BLOCKED / INCONCLUSIVE.

- BLOCKED: case chưa đủ bước tự động (quyết định trước khi mở trình duyệt).
- FAIL: một bước không đạt (Playwright quyết định), kèm số bước và ảnh chụp.
- INCONCLUSIVE: lỗi của chính worker (trình duyệt sập...) hoặc case chạy quá giờ.
- PASS: mọi bước đạt.

Mỗi case chạy trong một "ngữ cảnh" trình duyệt mới (không dính cookie, ô nhập của case trước),
nhưng bắt đầu từ phiên đăng nhập đã lưu của cả run.
"""

import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Browser, Page, StorageState

from app.core.models.run import ResultStatus
from app.core.models.test_case import AutoStep, TestCase
from app.worker.config import ProjectWorkerConfig
from app.worker.steps import StepFailed, run_step

MAX_ERROR_TEXT = 200


@dataclass(frozen=True)
class CaseOutcome:
    status: ResultStatus
    reason: str
    failed_step: int | None
    screenshot: Path | None


class LoginError(Exception):
    """Đăng nhập thất bại. Thông điệp không bao giờ chứa mật khẩu."""


def blocked_reason(case: TestCase) -> str | None:
    """Lý do case chưa chạy được, hoặc None nếu mọi bước đều có phần tự động."""
    if all(step.auto is None for step in case.steps):
        return "Chưa có bước tự động"
    for number, step in enumerate(case.steps, start=1):
        if step.auto is None:
            return f"Bước {number} chưa có phần tự động"
    return None


def perform_login(
    browser: Browser, config: ProjectWorkerConfig, *, step_timeout_ms: int
) -> StorageState:
    """Chạy `login_steps` một lần, trả về phiên đăng nhập (cookie...) để các case dùng lại."""
    context = browser.new_context()
    try:
        page = context.new_page()
        for number, step in enumerate(config.login_steps, start=1):
            filled = step.model_copy(
                update={
                    "value": step.value.replace("{email}", config.test_email).replace(
                        "{password}", config.test_password
                    )
                }
            )
            try:
                run_step(page, filled, config.app_url, timeout_ms=step_timeout_ms)
            except StepFailed as failure:
                message = str(failure).replace(config.test_password, "***")
                raise LoginError(f"Đăng nhập thất bại ở bước {number}: {message}") from None
        return context.storage_state()
    finally:
        context.close()


class CaseSession:
    def __init__(
        self,
        browser: Browser,
        storage_state: StorageState | None,
        base_url: str,
        artifacts_dir: Path,
        run_id: str,
        *,
        step_timeout_ms: int,
        case_timeout_seconds: float,
    ) -> None:
        self._browser = browser
        self._storage_state = storage_state
        self._base_url = base_url
        self._artifacts_dir = artifacts_dir
        self._run_id = run_id
        self._step_timeout_ms = step_timeout_ms
        self._case_timeout_seconds = case_timeout_seconds

    def run(self, case: TestCase) -> CaseOutcome:
        reason = blocked_reason(case)
        if reason is not None:
            return CaseOutcome(ResultStatus.BLOCKED, reason, None, None)

        deadline = time.monotonic() + self._case_timeout_seconds
        context = self._browser.new_context(storage_state=self._storage_state)
        try:
            return self._run_steps(context.new_page(), case, deadline)
        except Exception as error:  # lỗi của worker (trình duyệt sập...), không phải lỗi của app
            text = f"{type(error).__name__}: {error}"[:MAX_ERROR_TEXT]
            return CaseOutcome(ResultStatus.INCONCLUSIVE, f"Lỗi của worker: {text}", None, None)
        finally:
            context.close()

    def _run_steps(self, page: Page, case: TestCase, deadline: float) -> CaseOutcome:
        for number, step in enumerate(case.steps, start=1):
            auto: AutoStep | None = step.auto
            if auto is None:  # blocked_reason đã chặn; chỉ để thoả mypy
                continue
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                return self._timed_out()
            # Thời gian một bước không được vượt phần còn lại của case.
            capped = remaining_ms < self._step_timeout_ms
            try:
                run_step(
                    page, auto, self._base_url, timeout_ms=min(self._step_timeout_ms, remaining_ms)
                )
            except StepFailed as failure:
                if capped:
                    return self._timed_out()
                return CaseOutcome(
                    ResultStatus.FAIL, str(failure), number, self._take_screenshot(page, case)
                )
        return CaseOutcome(ResultStatus.PASS, "", None, None)

    def _timed_out(self) -> CaseOutcome:
        reason = f"Case chạy quá {self._case_timeout_seconds:g} giây"
        return CaseOutcome(ResultStatus.INCONCLUSIVE, reason, None, None)

    def _take_screenshot(self, page: Page, case: TestCase) -> Path | None:
        path = self._artifacts_dir / self._run_id / f"{case.id}.png"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(path))
        except Exception:  # không chụp được ảnh thì vẫn ghi FAIL, chỉ thiếu ảnh
            return None
        return path

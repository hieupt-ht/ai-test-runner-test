"""Thực hiện MỘT bước tự động bằng Playwright.

Lỗi "không đạt" (không thấy phần tử, sai chữ, sai URL, quá giờ) là `StepFailed` với thông điệp
tiếng Việt, để case được ghi FAIL. Lỗi khác của Playwright (trình duyệt sập...) không bị bắt ở
đây: đó là lỗi của worker chứ không phải lỗi của app đang test.
"""

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from app.core.models.test_case import AutoStep, AutoTarget, AutoType, TargetBy


class StepFailed(Exception):
    """Bước không đạt. Thông điệp tiếng Việt, hiện thẳng cho người dùng."""


def _describe(target: AutoTarget) -> str:
    match target.by:
        case TargetBy.TEXT:
            return f'chữ "{target.value}"'
        case TargetBy.LABEL:
            return f'ô có nhãn "{target.value}"'
        case TargetBy.CSS:
            return f'phần tử "{target.value}"'


def _locator(page: Page, target: AutoTarget) -> Locator:
    match target.by:
        case TargetBy.TEXT:
            # "Chữ hiển thị" phải khớp CẢ chữ (không phải một phần của chữ khác), nếu không
            # "Đăng nhập" sẽ khớp nhầm tiêu đề "Trang đăng nhập" nằm trước nút.
            value = target.value
            return (
                page.get_by_role("button", name=value, exact=True)
                .or_(page.get_by_role("link", name=value, exact=True))
                .or_(page.get_by_text(value, exact=True))
                .first
            )
        case TargetBy.LABEL:
            return page.get_by_label(target.value).first
        case TargetBy.CSS:
            return page.locator(target.value).first


def _absolute(base_url: str, value: str) -> str:
    return value if value.startswith(("http://", "https://")) else base_url.rstrip("/") + value


def _same_url(left: str, right: str) -> bool:
    return left.rstrip("/") == right.rstrip("/")


def run_step(page: Page, step: AutoStep, base_url: str, *, timeout_ms: int) -> None:
    target = step.target
    try:
        match step.type:
            case AutoType.GOTO:
                _goto(page, _absolute(base_url, step.value), timeout_ms)
            case AutoType.FILL if target is not None:
                _locator(page, target).fill(step.value, timeout=timeout_ms)
            case AutoType.CLICK if target is not None:
                _locator(page, target).click(timeout=timeout_ms)
            case AutoType.SELECT if target is not None:
                _locator(page, target).select_option(label=step.value, timeout=timeout_ms)
            case AutoType.SEE_TEXT:
                _see_text(page, step.value, timeout_ms)
            case AutoType.NOT_SEE_TEXT:
                _not_see_text(page, step.value, timeout_ms)
            case AutoType.URL_IS:
                _url_is(page, _absolute(base_url, step.value), timeout_ms)
            case _:
                raise StepFailed(f'Bước "{step.type.value}" thiếu phần tử cần thao tác')
    except PlaywrightTimeout as error:
        raise StepFailed(_timeout_message(step)) from error


def _timeout_message(step: AutoStep) -> str:
    if step.target is not None:
        return f"Không thấy {_describe(step.target)} trên trang"
    return f'Bước "{step.type.value}" quá giờ chờ'


def _goto(page: Page, url: str, timeout_ms: int) -> None:
    try:
        page.goto(url, timeout=timeout_ms)
    except PlaywrightTimeout:
        raise
    except PlaywrightError as error:
        raise StepFailed(f"Không mở được trang {url}") from error


def _see_text(page: Page, text: str, timeout_ms: int) -> None:
    try:
        page.get_by_text(text).first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeout as error:
        raise StepFailed(f'Không thấy chữ "{text}" trên trang') from error


def _not_see_text(page: Page, text: str, timeout_ms: int) -> None:
    try:
        # Không có phần tử nào cũng được coi là "không hiện".
        page.get_by_text(text).first.wait_for(state="hidden", timeout=timeout_ms)
    except PlaywrightTimeout as error:
        raise StepFailed(f'Chữ "{text}" vẫn đang hiện trên trang') from error


def _url_is(page: Page, expected: str, timeout_ms: int) -> None:
    try:
        page.wait_for_url(lambda url: _same_url(url, expected), timeout=timeout_ms)
    except PlaywrightTimeout as error:
        raise StepFailed(f'URL hiện tại là "{page.url}", mong đợi "{expected}"') from error

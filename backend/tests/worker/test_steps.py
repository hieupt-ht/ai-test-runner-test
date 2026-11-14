import pytest
from playwright.sync_api import Page

from app.core.models.test_case import AutoStep, AutoTarget, AutoType, TargetBy
from app.worker.steps import StepFailed, run_step

TIMEOUT_MS = 800


def goto(path: str) -> AutoStep:
    return AutoStep(type=AutoType.GOTO, value=path)


def on(by: TargetBy, value: str) -> AutoTarget:
    return AutoTarget(by=by, value=value)


def run(page: Page, site: str, step: AutoStep) -> None:
    run_step(page, step, site, timeout_ms=TIMEOUT_MS)


def test_goto_opens_relative_path(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    assert page.url == f"{site}/form"


def test_goto_unreachable_page_fails(page: Page, site: str) -> None:
    with pytest.raises(StepFailed, match="Không mở được trang"):
        run(page, "http://127.0.0.1:1", goto("/form"))


def test_fill_by_label(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    run(page, site, AutoStep(type=AutoType.FILL, target=on(TargetBy.LABEL, "Họ tên"), value="An"))

    assert page.input_value("#name") == "An"


def test_fill_missing_field_fails_with_vietnamese_message(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    step = AutoStep(type=AutoType.FILL, target=on(TargetBy.LABEL, "Số điện thoại"), value="1")
    with pytest.raises(StepFailed, match='Không thấy ô có nhãn "Số điện thoại"'):
        run(page, site, step)


def test_click_by_text_shows_message(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    run(page, site, AutoStep(type=AutoType.CLICK, target=on(TargetBy.TEXT, "Gửi")))

    assert page.is_visible("#done")


def test_click_by_css(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    run(page, site, AutoStep(type=AutoType.CLICK, target=on(TargetBy.CSS, "#send")))

    assert page.is_visible("#done")


def test_click_missing_text_fails(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    step = AutoStep(type=AutoType.CLICK, target=on(TargetBy.TEXT, "Nút không có"))
    with pytest.raises(StepFailed, match='Không thấy chữ "Nút không có"'):
        run(page, site, step)


def test_select_by_visible_label(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    step = AutoStep(type=AutoType.SELECT, target=on(TargetBy.LABEL, "Thành phố"), value="Đà Nẵng")
    run(page, site, step)

    assert page.input_value("#city") == "dn"


def test_select_missing_option_fails(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    step = AutoStep(type=AutoType.SELECT, target=on(TargetBy.LABEL, "Thành phố"), value="Huế")
    with pytest.raises(StepFailed):
        run(page, site, step)


def test_see_text_passes_when_text_is_visible(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    run(page, site, AutoStep(type=AutoType.SEE_TEXT, value="Biểu mẫu"))


def test_see_text_fails_when_text_is_missing(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    with pytest.raises(StepFailed, match='Không thấy chữ "Đã gửi"'):
        run(page, site, AutoStep(type=AutoType.SEE_TEXT, value="Đã gửi"))


def test_not_see_text_passes_when_text_is_hidden_or_absent(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    run(page, site, AutoStep(type=AutoType.NOT_SEE_TEXT, value="Đã gửi"))  # có nhưng đang ẩn
    run(page, site, AutoStep(type=AutoType.NOT_SEE_TEXT, value="Không có chữ này"))


def test_not_see_text_fails_when_text_is_visible(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    with pytest.raises(StepFailed, match='Chữ "Biểu mẫu" vẫn đang hiện'):
        run(page, site, AutoStep(type=AutoType.NOT_SEE_TEXT, value="Biểu mẫu"))


def test_url_is_passes_with_path_and_full_url(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    run(page, site, AutoStep(type=AutoType.URL_IS, value="/form"))
    run(page, site, AutoStep(type=AutoType.URL_IS, value=f"{site}/form"))


def test_url_is_fails_and_names_both_urls(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    with pytest.raises(StepFailed, match=r"/form.*\/home|\/home.*\/form"):
        run(page, site, AutoStep(type=AutoType.URL_IS, value="/home"))


def test_step_timeout_message_is_vietnamese(page: Page, site: str) -> None:
    run(page, site, goto("/form"))

    with pytest.raises(StepFailed) as error:
        run_step(
            page,
            AutoStep(type=AutoType.CLICK, target=on(TargetBy.TEXT, "Không có")),
            site,
            timeout_ms=300,
        )

    assert str(error.value).startswith("Không thấy")


def test_click_text_matches_whole_text_not_a_heading_containing_it(
    page: Page, site: str
) -> None:
    """Trang /login có tiêu đề "Trang đăng nhập" nằm trước nút "Đăng nhập"."""
    run(page, site, goto("/login"))

    run(page, site, AutoStep(type=AutoType.CLICK, target=on(TargetBy.TEXT, "Đăng nhập")))

    run(page, site, AutoStep(type=AutoType.URL_IS, value="/home"))


def test_click_text_prefers_the_button_over_a_heading_with_the_same_text(
    page: Page, site: str
) -> None:
    """Tiêu đề h2 "Đăng nhập" đứng trước nút "Đăng nhập": phải bấm nút, không bấm tiêu đề."""
    run(page, site, goto("/signin"))

    run(page, site, AutoStep(type=AutoType.CLICK, target=on(TargetBy.TEXT, "Đăng nhập")))

    run(page, site, AutoStep(type=AutoType.URL_IS, value="/form"))

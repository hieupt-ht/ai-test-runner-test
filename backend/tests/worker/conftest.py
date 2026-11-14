from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from tests.worker.site import serve


@pytest.fixture(scope="session")
def site() -> Iterator[str]:
    with serve() as base_url:
        yield base_url


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch(headless=True)
        except Exception as error:
            pytest.skip(f'Chưa cài Chromium: chạy "uv run playwright install chromium" ({error})')
        yield chromium
        chromium.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context()
    yield context.new_page()
    context.close()

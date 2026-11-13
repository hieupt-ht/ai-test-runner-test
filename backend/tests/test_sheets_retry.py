import pytest
from googleapiclient.errors import HttpError

from app.core.sheets.gateway import with_retry
from tests.fakes import make_http_error


def test_retry_on_429_then_success() -> None:
    calls = {"count": 0}

    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise make_http_error(429)
        return "ok"

    delays: list[float] = []

    assert with_retry(flaky, sleep=delays.append) == "ok"
    assert len(delays) == 2
    assert delays[1] > delays[0]  # chờ lâu dần (exponential backoff)


def test_retry_gives_up_after_max_attempts() -> None:
    calls = {"count": 0}

    def always_503() -> str:
        calls["count"] += 1
        raise make_http_error(503)

    with pytest.raises(HttpError):
        with_retry(always_503, max_attempts=5, sleep=lambda _: None)
    assert calls["count"] == 5


def test_no_retry_on_404() -> None:
    calls = {"count": 0}

    def not_found() -> str:
        calls["count"] += 1
        raise make_http_error(404)

    with pytest.raises(HttpError):
        with_retry(not_found, sleep=lambda _: None)
    assert calls["count"] == 1

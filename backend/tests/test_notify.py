from unittest.mock import Mock

import pytest

from app.core.notifications import NotificationStore
from app.core.services.notify import Notifier


@pytest.mark.parametrize(
    ("method", "kwargs", "email", "link"),
    [
        (
            "member_added",
            {"email": "an@x.com", "project_id": "P1", "project_name": "Web"},
            "an@x.com",
            "/projects/P1",
        ),
        (
            "screen_assigned",
            {
                "email": "an@x.com",
                "project_id": "P1",
                "screen_id": "S1",
                "screen_name": "Đăng nhập",
            },
            "an@x.com",
            "/projects/P1/screens",
        ),
        (
            "case_returned",
            {"email": "an@x.com", "project_id": "P1", "case_id": "C1", "comment": "Sửa bước 2"},
            "an@x.com",
            "/projects/P1/test-cases/C1",
        ),
        (
            "case_approved",
            {"email": "an@x.com", "project_id": "P1", "case_id": "C1"},
            "an@x.com",
            "/projects/P1/test-cases/C1",
        ),
        (
            "case_submitted",
            {"emails": ["lead@x.com"], "project_id": "P1", "case_id": "C1"},
            "lead@x.com",
            "/projects/P1/test-cases/C1",
        ),
        (
            "results_recorded",
            {"emails": ["an@x.com"], "project_id": "P1", "run_id": "R1", "failed": 1, "total": 2},
            "an@x.com",
            "/projects/P1/results",
        ),
    ],
)
def test_event_creates_notification(
    method: str, kwargs: dict[str, object], email: str, link: str
) -> None:
    store = Mock(spec=NotificationStore)

    getattr(Notifier(store), method)(**kwargs)

    store.add.assert_called_once()
    assert store.add.call_args.args == (email,)
    assert store.add.call_args.kwargs["link"] == link
    assert store.add.call_args.kwargs["title"]


def test_results_recorded_deduplicates_recipients() -> None:
    store = Mock(spec=NotificationStore)

    Notifier(store).results_recorded(
        emails=["an@x.com", "an@x.com", "lead@x.com"],
        project_id="P1",
        run_id="R1",
        failed=1,
        total=2,
    )

    assert store.add.call_count == 2


def test_store_error_does_not_raise() -> None:
    store = Mock(spec=NotificationStore)
    store.add.side_effect = RuntimeError("Redis lỗi")

    Notifier(store).member_added(email="an@x.com", project_id="P1", project_name="Web")


def test_none_store_is_noop() -> None:
    Notifier(None).case_approved(email="an@x.com", project_id="P1", case_id="C1")

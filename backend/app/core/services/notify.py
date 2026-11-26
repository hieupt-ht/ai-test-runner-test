"""Phát thông báo trong app; lỗi Redis không làm hỏng thao tác chính."""

import logging

from app.core.notifications import NotificationStore

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, store: NotificationStore | None) -> None:
        self._store = store

    def _send(self, email: str, *, type: str, title: str, link: str) -> None:
        if self._store is None:
            return
        try:
            self._store.add(email, type=type, title=title, link=link)
        except Exception:
            logger.warning("Không gửi được thông báo loại %s", type, exc_info=True)

    def member_added(self, *, email: str, project_id: str, project_name: str) -> None:
        self._send(
            email, type="member_added", title=f"Bạn được thêm vào dự án {project_name}",
            link=f"/projects/{project_id}",
        )

    def screen_assigned(
        self, *, email: str, project_id: str, screen_id: str, screen_name: str
    ) -> None:
        self._send(
            email, type="screen_assigned", title=f"Bạn được giao màn hình {screen_name}",
            link=f"/projects/{project_id}/screens",
        )

    def module_assigned(
        self, *, email: str, project_id: str, module_id: str, module_name: str
    ) -> None:
        self._send(
            email, type="module_assigned", title=f"Bạn được giao module {module_name}",
            link=f"/projects/{project_id}/screens?module={module_id}",
        )

    def case_returned(
        self, *, email: str, project_id: str, case_id: str, comment: str
    ) -> None:
        self._send(
            email, type="case_returned", title=f"Case {case_id} bị trả lại: {comment}",
            link=f"/projects/{project_id}/test-cases/{case_id}",
        )

    def case_approved(self, *, email: str, project_id: str, case_id: str) -> None:
        self._send(
            email, type="case_approved", title=f"Case {case_id} đã được duyệt",
            link=f"/projects/{project_id}/test-cases/{case_id}",
        )

    def case_submitted(self, *, emails: list[str], project_id: str, case_id: str) -> None:
        for email in dict.fromkeys(emails):
            self._send(
                email,
                type="case_submitted",
                title=f"Case {case_id} đang chờ duyệt",
                link=f"/projects/{project_id}/test-cases/{case_id}",
            )

    def results_recorded(
        self, *, emails: list[str], project_id: str, run_id: str, failed: int, total: int
    ) -> None:
        for email in dict.fromkeys(emails):
            self._send(
                email, type="results_recorded",
                title=f"Lần chạy {run_id} đã xong: {failed}/{total} case FAIL",
                link=f"/projects/{project_id}/results",
            )

    def cases_imported(
        self, *, email: str, project_id: str, count: int, screen_names: list[str]
    ) -> None:
        self._send(
            email,
            type="cases_imported",
            title=f"Có {count} case mới cần chạy ở: {', '.join(screen_names)}",
            link=f"/projects/{project_id}/test-cases",
        )

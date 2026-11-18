"""Nghiệp vụ dự án: tạo (kiểm tra GitHub và Google Sheet), sửa, lưu trữ."""

from collections.abc import Callable
from typing import Any

from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.github.client import GitHubClient, GitHubNotConfiguredError
from app.core.models.project import Project, Storage
from app.core.models.user import Role, User
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import (
    SPREADSHEET_IN_USE,
    ProjectRepository,
    SpreadsheetInUseError,
)
from app.core.sheets.gateway import SheetAccessDeniedError, SheetsGateway
from app.core.sheets.spreadsheet_id import InvalidSpreadsheetError, parse_spreadsheet_id
from app.core.sheets.table import MissingColumnsError


class InvalidProjectInputError(Exception):
    """Dữ liệu nhập sai (trả 422). `str(error)` là câu báo lỗi tiếng Việt."""


class ProjectService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        members: ProjectMemberRepository,
        audit_log: AuditLogRepository,
        gateway: SheetsGateway,
        github: GitHubClient | None,
        system_spreadsheet_id: str,
        service_account_email: str,
    ) -> None:
        self._projects = projects
        self._members = members
        self._audit_log = audit_log
        self._gateway = gateway
        self._github = github
        self._system_spreadsheet_id = system_spreadsheet_id
        self._service_account_email = service_account_email

    def list_visible(self, user: User) -> list[Project]:
        """Admin thấy mọi dự án; người khác chỉ thấy dự án mình tham gia và chưa lưu trữ."""
        all_projects = self._projects.list_all()
        if user.role == Role.ADMIN:
            visible = all_projects
        else:
            my_ids = set(self._members.projects_of(user.email))
            visible = [p for p in all_projects if p.id in my_ids and not p.archived]
        return sorted(visible, key=lambda project: project.name.lower())

    def create_project(
        self,
        actor: User,
        *,
        name: str,
        repo_full_name: str,
        branch: str,
        staging_url: str,
        spreadsheet: str,
    ) -> Project:
        spreadsheet_id = self._parse_spreadsheet(spreadsheet)
        self._ensure_spreadsheet_unused(spreadsheet_id)
        self._ensure_repo_and_branch(repo_full_name, branch)
        self._prepare_project_sheet(spreadsheet_id)

        project = self._projects.create(
            name=name,
            repo_full_name=repo_full_name,
            branch=branch,
            staging_url=staging_url,
            spreadsheet_id=spreadsheet_id,
        )
        self._record(actor, "CREATE", project.id, project.model_dump(mode="json"))
        return project

    def update_project(
        self,
        actor: User,
        project: Project,
        *,
        name: str | None = None,
        branch: str | None = None,
        staging_url: str | None = None,
        archived: bool | None = None,
        android_app_id: str | None = None,
        ios_bundle_id: str | None = None,
        require_review: bool | None = None,
        storage: Storage | None = None,
        approve_pending: Callable[[], None] | None = None,
    ) -> Project:
        """`approve_pending` chạy khi công tắc "cần duyệt" đổi từ bật sang tắt."""
        if branch is not None and branch != project.branch:
            self._ensure_repo_and_branch(project.repo_full_name, branch)

        changes = {
            "name": name,
            "branch": branch,
            "staging_url": staging_url,
            "archived": archived,
            "android_app_id": android_app_id,
            "ios_bundle_id": ios_bundle_id,
            "require_review": require_review,
            "storage": storage,
        }
        updated = project.model_copy(
            update={field: value for field, value in changes.items() if value is not None}
        )
        old, new = project.model_dump(mode="json"), updated.model_dump(mode="json")
        diff = {field: [old[field], new[field]] for field in old if old[field] != new[field]}
        if not diff:
            return project

        # Duyệt trước rồi mới lưu công tắc: nếu duyệt lỗi thì công tắc vẫn bật, bấm lại được.
        turning_review_off = project.require_review and not updated.require_review
        if turning_review_off and approve_pending is not None:
            approve_pending()
        self._projects.update(updated)
        self._record(actor, "UPDATE", project.id, diff)
        return updated

    # ----- Các bước kiểm tra khi tạo dự án -----

    @staticmethod
    def _parse_spreadsheet(text: str) -> str:
        try:
            return parse_spreadsheet_id(text)
        except InvalidSpreadsheetError:
            raise InvalidProjectInputError("Link hoặc ID Google Sheet không hợp lệ") from None

    def _ensure_spreadsheet_unused(self, spreadsheet_id: str) -> None:
        is_system_sheet = spreadsheet_id == self._system_spreadsheet_id
        if is_system_sheet or self._projects.find_by_spreadsheet(spreadsheet_id):
            raise SpreadsheetInUseError(SPREADSHEET_IN_USE)

    def _ensure_repo_and_branch(self, repo_full_name: str, branch: str) -> None:
        if self._github is None:
            raise GitHubNotConfiguredError
        known_repos = {repo.full_name for repo in self._github.list_repositories()}
        if repo_full_name not in known_repos:
            raise InvalidProjectInputError("Repo không có trong danh sách GitHub App được cài")
        if branch not in self._github.list_branches(repo_full_name):
            raise InvalidProjectInputError(
                f"Không tìm thấy branch {branch} trong repo {repo_full_name}"
            )

    def _prepare_project_sheet(self, spreadsheet_id: str) -> None:
        try:
            bootstrap_project_spreadsheet(self._gateway, spreadsheet_id)
        except SheetAccessDeniedError:
            raise InvalidProjectInputError(
                "App chưa có quyền ghi vào Sheet này. Hãy share quyền Editor cho "
                f"{self._service_account_email}"
            ) from None
        except MissingColumnsError as error:
            # Sheet có sẵn tab trùng tên nhưng cột khác (ví dụ file cũ của nhóm khác)
            raise InvalidProjectInputError(
                f"Sheet này đã có tab nhưng sai cột: {error}. "
                "Hãy dùng một file Sheet mới, hoặc sửa lại hàng tiêu đề của tab đó."
            ) from None

    def _record(self, actor: User, action: str, project_id: str, diff: dict[str, Any]) -> None:
        self._audit_log.record(
            actor=actor.email, action=action, entity="project", entity_id=project_id, diff=diff
        )

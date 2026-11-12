"""Nghiệp vụ dự án: tạo (kiểm tra GitHub và Google Sheet), sửa, lưu trữ."""

from typing import Any

from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.github.client import GitHubClient, GitHubNotConfiguredError
from app.core.models.project import Project
from app.core.models.user import Role, User
from app.core.repositories.audit_log import AuditLogRepository
from app.core.repositories.members import ProjectMemberRepository
from app.core.repositories.projects import ProjectRepository
from app.core.sheets.gateway import SheetAccessDeniedError, SheetsGateway
from app.core.sheets.spreadsheet_id import InvalidSpreadsheetError, parse_spreadsheet_id


class InvalidProjectInputError(Exception):
    """Dữ liệu nhập sai (trả 422). `str(error)` là câu báo lỗi tiếng Việt."""


class SpreadsheetInUseError(Exception):
    pass


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
    ) -> Project:
        if branch is not None and branch != project.branch:
            self._ensure_repo_and_branch(project.repo_full_name, branch)

        changes = {"name": name, "branch": branch, "staging_url": staging_url, "archived": archived}
        updated = project.model_copy(
            update={field: value for field, value in changes.items() if value is not None}
        )
        old, new = project.model_dump(mode="json"), updated.model_dump(mode="json")
        diff = {field: [old[field], new[field]] for field in old if old[field] != new[field]}
        if not diff:
            return project

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
            raise SpreadsheetInUseError("Google Sheet này đã được dùng cho dự án khác")

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

    def _record(self, actor: User, action: str, project_id: str, diff: dict[str, Any]) -> None:
        self._audit_log.record(
            actor=actor.email, action=action, entity="project", entity_id=project_id, diff=diff
        )

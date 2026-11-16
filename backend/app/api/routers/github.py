from fastapi import APIRouter

from app.api.deps import CurrentUser, ServicesDep, require
from app.api.errors import github_http_error
from app.api.services import Services
from app.core.github.client import (
    GitHubClient,
    GitHubError,
    GitHubNotConfiguredError,
    RepoInfo,
)
from app.core.permissions import Action

router = APIRouter(prefix="/api/github", tags=["github"])


def _github(services: Services) -> GitHubClient:
    if services.github is None:
        raise github_http_error(GitHubNotConfiguredError())
    return services.github


@router.get("/repositories")
def list_repositories(user: CurrentUser, services: ServicesDep) -> list[RepoInfo]:
    """Các repo mà GitHub App đang được cài, để Admin chọn khi tạo dự án."""
    require(user, Action.MANAGE_PROJECTS)
    try:
        return _github(services).list_repositories()
    except GitHubError as error:
        raise github_http_error(error) from None


@router.get("/repositories/{owner}/{repo}/branches")
def list_branches(owner: str, repo: str, user: CurrentUser, services: ServicesDep) -> list[str]:
    require(user, Action.MANAGE_PROJECTS)
    try:
        return _github(services).list_branches(f"{owner}/{repo}")
    except GitHubError as error:
        raise github_http_error(error) from None

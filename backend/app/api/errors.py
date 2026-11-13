from fastapi import HTTPException, status

from app.core.github.client import GitHubNotConfiguredError


def github_http_error(error: Exception) -> HTTPException:
    """Đổi lỗi GitHub thành phản hồi HTTP có câu báo tiếng Việt."""
    if isinstance(error, GitHubNotConfiguredError):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Chưa cấu hình GitHub App. Xem README."
        )
    return HTTPException(status.HTTP_502_BAD_GATEWAY, str(error))

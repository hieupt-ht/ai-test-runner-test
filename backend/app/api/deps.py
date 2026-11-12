"""Các "dependency" của FastAPI: lấy services, lấy user đang đăng nhập, kiểm tra quyền."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.api.services import Services
from app.api.sessions import SESSION_COOKIE
from app.core.models.user import User
from app.core.permissions import Action, can


def get_services(request: Request) -> Services:
    services: Services | None = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Hệ thống chưa được cấu hình Google Sheets. Xem README.",
        )
    return services


ServicesDep = Annotated[Services, Depends(get_services)]


def get_current_user(request: Request, services: ServicesDep) -> User:
    not_logged_in = HTTPException(status.HTTP_401_UNAUTHORIZED, "Bạn cần đăng nhập")

    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise not_logged_in

    email = services.sessions.get_email(session_id)
    if email is None:
        raise not_logged_in

    user = services.users.get(email)
    if user is None or not user.active:
        raise not_logged_in
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(
    user: User, action: Action, *, is_member: bool = False, owns_or_assigned: bool = False
) -> None:
    if not can(user, action, is_member=is_member, owns_or_assigned=owns_or_assigned):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Bạn không có quyền thực hiện thao tác này"
        )

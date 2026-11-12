"""Phân quyền theo bảng ở spec mục 4.

Hàm `can` chỉ trả lời "được hay không". Việc trả HTTP 403 nằm ở `app/api/deps.py`.
"""

from enum import StrEnum

from app.core.models.user import Role, User


class Action(StrEnum):
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_PROJECTS = "MANAGE_PROJECTS"
    MANAGE_MEMBERS = "MANAGE_MEMBERS"
    MANAGE_SCREENS = "MANAGE_SCREENS"
    EDIT_TEST_CASE = "EDIT_TEST_CASE"
    REVIEW_TEST_CASE = "REVIEW_TEST_CASE"
    TRIGGER_RUN = "TRIGGER_RUN"
    REVIEW_RESULTS = "REVIEW_RESULTS"
    VIEW_PROJECT = "VIEW_PROJECT"


_EVERYONE = {Role.ADMIN, Role.QA_LEAD, Role.TESTER, Role.VIEWER}
_LEADS = {Role.ADMIN, Role.QA_LEAD}

ALLOWED_ROLES: dict[Action, set[Role]] = {
    Action.MANAGE_USERS: {Role.ADMIN},
    Action.MANAGE_PROJECTS: {Role.ADMIN},
    Action.MANAGE_MEMBERS: _LEADS,
    Action.MANAGE_SCREENS: _LEADS,
    Action.EDIT_TEST_CASE: _LEADS | {Role.TESTER},
    Action.REVIEW_TEST_CASE: _LEADS,
    Action.TRIGGER_RUN: _LEADS,
    Action.REVIEW_RESULTS: _LEADS,
    Action.VIEW_PROJECT: _EVERYONE,
}

# Việc cấp hệ thống: không gắn với dự án nào, nên không cần là thành viên.
SYSTEM_ACTIONS = {Action.MANAGE_USERS, Action.MANAGE_PROJECTS}


def can(
    user: User, action: Action, *, is_member: bool = False, owns_or_assigned: bool = False
) -> bool:
    if not user.active:
        return False
    if user.role not in ALLOWED_ROLES[action]:
        return False
    if user.role == Role.ADMIN:
        return True  # Admin làm được mọi việc mình có quyền, ở mọi dự án

    needs_membership = action not in SYSTEM_ACTIONS
    if needs_membership and not is_member:
        return False

    # Tester chỉ sửa được case mình tạo, hoặc case thuộc màn hình được giao cho mình.
    if user.role == Role.TESTER and action == Action.EDIT_TEST_CASE:
        return owns_or_assigned

    return True

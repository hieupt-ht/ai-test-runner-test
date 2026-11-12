"""Bảng phân quyền ở spec mục 4, viết lại thành dữ liệu để test."""

import pytest

from app.core.models.user import Role
from app.core.permissions import Action, can
from tests.conftest import make_user

A, Q, T, V = Role.ADMIN, Role.QA_LEAD, Role.TESTER, Role.VIEWER

# Ai được làm gì, khi đã là thành viên dự án và (với Tester) case là của mình.
SPEC_TABLE: dict[Action, set[Role]] = {
    Action.MANAGE_USERS: {A},
    Action.MANAGE_PROJECTS: {A},
    Action.MANAGE_MEMBERS: {A, Q},
    Action.MANAGE_SCREENS: {A, Q},
    Action.EDIT_TEST_CASE: {A, Q, T},
    Action.REVIEW_TEST_CASE: {A, Q},
    Action.TRIGGER_RUN: {A, Q},
    Action.REVIEW_RESULTS: {A, Q},
    Action.VIEW_PROJECT: {A, Q, T, V},
}


@pytest.mark.parametrize("action", list(Action))
@pytest.mark.parametrize("role", list(Role))
def test_permission_matrix_matches_spec(role: Role, action: Action) -> None:
    user = make_user("u@x.com", role=role)

    allowed = can(user, action, is_member=True, owns_or_assigned=True)

    assert allowed == (role in SPEC_TABLE[action])


@pytest.mark.parametrize(
    ("role", "action", "is_member", "owns", "expected"),
    [
        (Q, Action.MANAGE_SCREENS, False, False, False),  # QA Lead không phải thành viên
        (T, Action.EDIT_TEST_CASE, True, False, False),  # case không phải của mình
        (T, Action.EDIT_TEST_CASE, False, True, False),  # không phải thành viên
        (V, Action.VIEW_PROJECT, False, False, False),
        (A, Action.VIEW_PROJECT, False, False, True),  # Admin thấy mọi dự án
        (A, Action.TRIGGER_RUN, False, False, True),
        (A, Action.MANAGE_USERS, False, False, True),  # việc cấp hệ thống, không cần thành viên
    ],
)
def test_membership_and_ownership_rules(
    role: Role, action: Action, is_member: bool, owns: bool, expected: bool
) -> None:
    user = make_user("u@x.com", role=role)

    assert can(user, action, is_member=is_member, owns_or_assigned=owns) == expected


@pytest.mark.parametrize("action", list(Action))
def test_inactive_user_can_do_nothing(action: Action) -> None:
    user = make_user("u@x.com", role=Role.ADMIN, active=False)

    assert not can(user, action, is_member=True, owns_or_assigned=True)

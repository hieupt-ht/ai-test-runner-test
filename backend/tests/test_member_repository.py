import pytest

from app.core.repositories.members import (
    MemberAlreadyExistsError,
    MemberNotFoundError,
    ProjectMemberRepository,
)
from tests.conftest import SYSTEM_SHEET_ID
from tests.fakes import FakeSheetsGateway


def test_add_and_is_member_normalizes_email(members: ProjectMemberRepository) -> None:
    members.add("PRJ-0001", " An@X.com")

    assert members.is_member("PRJ-0001", "an@x.com")
    assert not members.is_member("PRJ-0002", "an@x.com")
    assert members.projects_of("AN@x.com") == ["PRJ-0001"]


def test_add_duplicate_raises(members: ProjectMemberRepository) -> None:
    members.add("PRJ-0001", "an@x.com")

    with pytest.raises(MemberAlreadyExistsError):
        members.add("PRJ-0001", "AN@x.com")


def test_remove_deletes_only_that_row(
    members: ProjectMemberRepository, gateway: FakeSheetsGateway
) -> None:
    members.add("PRJ-0001", "an@x.com")
    members.add("PRJ-0001", "binh@x.com")
    members.add("PRJ-0002", "an@x.com")

    members.remove("PRJ-0001", "an@x.com")

    rows = gateway.data[SYSTEM_SHEET_ID]["ProjectMembers"][1:]
    assert [row[:2] for row in rows] == [["PRJ-0001", "binh@x.com"], ["PRJ-0002", "an@x.com"]]


def test_remove_invalidates_cache(members: ProjectMemberRepository) -> None:
    members.add("PRJ-0001", "an@x.com")
    assert members.is_member("PRJ-0001", "an@x.com")  # nạp cache

    members.remove("PRJ-0001", "an@x.com")

    assert not members.is_member("PRJ-0001", "an@x.com")


def test_remove_unknown_member_raises(members: ProjectMemberRepository) -> None:
    with pytest.raises(MemberNotFoundError):
        members.remove("PRJ-0001", "khong-co@x.com")


def test_list_for_project(members: ProjectMemberRepository) -> None:
    members.add("PRJ-0001", "an@x.com")
    members.add("PRJ-0002", "binh@x.com")

    assert [member.email for member in members.list_for_project("PRJ-0001")] == ["an@x.com"]

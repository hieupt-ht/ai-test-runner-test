"""Cách chạy của test case: Manual (mặc định) hoặc Automation (agent chạy)."""


import fakeredis
import pytest

from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.models.test_case import (
    CHANGED_FIELD_LABELS,
    ExecutionMode,
    Priority,
    Severity,
    TestCaseContent,
    TestStep,
)
from app.core.repositories.test_cases import TestCaseRepository
from tests.fakes import FakeSheetsGateway
from tests.test_test_case_repository import SHEET, make_content


@pytest.fixture
def repo(gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis) -> TestCaseRepository:
    gateway.data.setdefault(SHEET, {})
    bootstrap_project_spreadsheet(gateway, SHEET)
    return TestCaseRepository(gateway, SHEET, redis, "PRJ-0001", lock_wait_seconds=0.1)


def test_new_content_defaults_to_manual() -> None:
    content = TestCaseContent(
        title="Đăng nhập",
        steps=[TestStep(action="Mở trang")],
        expected_result="Vào được",
        severity=Severity.HIGH,
        priority=Priority.P1,
    )
    assert content.execution_mode == ExecutionMode.MANUAL


def test_execution_mode_round_trips_through_sheet(
    repo: TestCaseRepository, gateway: FakeSheetsGateway
) -> None:
    content = make_content().model_copy(update={"execution_mode": ExecutionMode.AUTOMATION})
    created = repo.create(screen_id="SC-0001", content=content, actor="an@x.com")

    header, row = gateway.data[SHEET]["TestCases"][:2]
    assert row[header.index("execution_mode")] == "AUTOMATION"
    loaded = repo.get(created.id)
    assert loaded is not None and loaded.execution_mode == ExecutionMode.AUTOMATION


def test_blank_cell_reads_as_automation(
    repo: TestCaseRepository, gateway: FakeSheetsGateway
) -> None:
    created = repo.create(screen_id="SC-0001", content=make_content(), actor="an@x.com")
    header = gateway.data[SHEET]["TestCases"][0]
    gateway.data[SHEET]["TestCases"][1][header.index("execution_mode")] = ""

    loaded = repo.get(created.id)

    assert loaded is not None and loaded.execution_mode == ExecutionMode.AUTOMATION


def test_execution_mode_has_vietnamese_label() -> None:
    assert CHANGED_FIELD_LABELS["execution_mode"] == "Cách chạy"



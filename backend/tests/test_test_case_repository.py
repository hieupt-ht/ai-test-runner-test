import threading
from collections.abc import Callable

import fakeredis
import pytest

from app.core.bootstrap import bootstrap_project_spreadsheet
from app.core.models.test_case import (
    AutoStep,
    AutoTarget,
    AutoType,
    Priority,
    Severity,
    TargetBy,
    TestCaseContent,
    TestCaseStatus,
    TestStep,
)
from app.core.repositories.test_cases import (
    TestCaseNotFoundError,
    TestCaseRepository,
    VersionConflictError,
)
from tests.fakes import FakeSheetsGateway

SHEET = "project-sheet"
AN = "an@x.com"
BINH = "binh@x.com"


def make_content(title: str = "Đăng nhập thành công") -> TestCaseContent:
    return TestCaseContent(
        title=title,
        steps=[
            TestStep(action="Mở trang", expected="Thấy form"),
            TestStep(action="Bấm Đăng nhập", expected=""),
        ],
        expected_result="Vào được trang chủ",
        severity=Severity.HIGH,
        priority=Priority.P1,
    )


@pytest.fixture
def repo_factory(
    gateway: FakeSheetsGateway, redis: fakeredis.FakeRedis
) -> Callable[[], TestCaseRepository]:
    gateway.data.setdefault(SHEET, {})
    bootstrap_project_spreadsheet(gateway, SHEET)

    def build() -> TestCaseRepository:
        return TestCaseRepository(gateway, SHEET, redis, "PRJ-0001", lock_wait_seconds=0.1)

    return build


@pytest.fixture
def repo(repo_factory: Callable[[], TestCaseRepository]) -> TestCaseRepository:
    return repo_factory()


def test_create_starts_as_draft_version_1(
    repo: TestCaseRepository, gateway: FakeSheetsGateway
) -> None:
    case = repo.create(
        screen_id="SC-0001",
        content=TestCaseContent(
            title="Mở form",
            steps=[TestStep(action="Mở trang", expected="Thấy form")],
            expected_result="Có form",
            severity=Severity.LOW,
            priority=Priority.P3,
        ),
        actor=AN,
    )

    assert case.id == "TC-000001"
    assert case.status == TestCaseStatus.DRAFT
    assert case.version == 1
    assert case.created_by == case.updated_by == AN
    header, row = gateway.data[SHEET]["TestCases"][:2]
    assert row[header.index("steps")] == '[{"action": "Mở trang", "expected": "Thấy form"}]'


def test_round_trip_keeps_vietnamese_and_step_order(repo: TestCaseRepository) -> None:
    created = repo.create(screen_id="SC-0001", content=make_content(), actor=AN)

    loaded = repo.get(created.id)

    assert loaded == created
    assert loaded is not None
    assert loaded.title == "Đăng nhập thành công"
    assert [step.action for step in loaded.steps] == ["Mở trang", "Bấm Đăng nhập"]
    assert repo.list_all() == [created]


def test_save_with_matching_version_increments(repo: TestCaseRepository) -> None:
    created = repo.create(screen_id="SC-0001", content=make_content(), actor=AN)

    saved = repo.save(
        created.model_copy(update={"title": "Tên mới"}), expected_version=1, actor=BINH
    )

    assert saved.version == 2
    assert saved.updated_by == BINH
    assert saved.created_by == AN
    assert repo.get(created.id) == saved


def test_save_with_stale_version_raises_conflict(
    repo_factory: Callable[[], TestCaseRepository],
) -> None:
    repo = repo_factory()
    created = repo.create(screen_id="SC-0001", content=make_content(), actor=AN)
    copy_a = repo.get(created.id)
    copy_b = repo.get(created.id)
    assert copy_a is not None and copy_b is not None

    repo.save(copy_a.model_copy(update={"title": "Bản của A"}), expected_version=1, actor=AN)
    with pytest.raises(VersionConflictError) as error:
        repo.save(copy_b.model_copy(update={"title": "Bản của B"}), expected_version=1, actor=BINH)

    assert error.value.latest.version == 2
    assert error.value.latest.updated_by == AN
    stored = repo.get(created.id)
    assert stored is not None
    assert stored.title == "Bản của A"


def test_save_unknown_case_raises(repo: TestCaseRepository) -> None:
    created = repo.create(screen_id="SC-0001", content=make_content(), actor=AN)
    ghost = created.model_copy(update={"id": "TC-999999"})

    with pytest.raises(TestCaseNotFoundError):
        repo.save(ghost, expected_version=1, actor=AN)


def test_parallel_creates_get_distinct_ids(
    repo_factory: Callable[[], TestCaseRepository],
) -> None:
    ids: list[str] = []
    guard = threading.Lock()

    def worker() -> None:
        own_repo = repo_factory()
        for _ in range(5):
            case = own_repo.create(screen_id="SC-0001", content=make_content(), actor=AN)
            with guard:
                ids.append(case.id)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(set(ids)) == 10
    assert len(repo_factory().list_all()) == 10


def test_get_reads_only_id_column_and_one_row(
    repo: TestCaseRepository, gateway: FakeSheetsGateway
) -> None:
    for number in range(3):
        repo.create(screen_id="SC-0001", content=make_content(f"Case {number}"), actor=AN)
    gateway.calls.clear()

    found = repo.get("TC-000002")

    assert found is not None and found.title == "Case 1"
    assert "TestCases" not in gateway.calls  # không đọc cả tab
    assert repo.get("TC-009999") is None


def _steps_cell(gateway: FakeSheetsGateway, row_index: int = 1) -> str:
    rows = gateway.data[SHEET]["TestCases"]
    return rows[row_index][rows[0].index("steps")]


def test_auto_step_round_trips_through_sheet(
    repo_factory: Callable[[], TestCaseRepository],
) -> None:
    auto = AutoStep(
        type=AutoType.FILL, target=AutoTarget(by=TargetBy.LABEL, value="Email"), value="qa@x.com"
    )
    content = make_content()
    content.steps[0] = TestStep(action="Nhập email", expected="", auto=auto)
    created = repo_factory().create(screen_id="SC-0001", content=content, actor=AN)

    loaded = repo_factory().get(created.id)

    assert loaded is not None
    assert loaded.steps[0].auto == auto
    assert loaded.steps[1].auto is None


def test_record_without_auto_loads(
    repo: TestCaseRepository, gateway: FakeSheetsGateway
) -> None:
    created = repo.create(screen_id="SC-0001", content=make_content(), actor=AN)
    rows = gateway.data[SHEET]["TestCases"]
    rows[1][rows[0].index("steps")] = '[{"action": "Mở trang", "expected": "Thấy form"}]'

    loaded = repo.get(created.id)

    assert loaded is not None
    assert loaded.steps[0].auto is None


def test_steps_without_auto_do_not_write_auto_key(
    repo: TestCaseRepository, gateway: FakeSheetsGateway
) -> None:
    repo.create(screen_id="SC-0001", content=make_content(), actor=AN)

    assert "auto" not in _steps_cell(gateway)

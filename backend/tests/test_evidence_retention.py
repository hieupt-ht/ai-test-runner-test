"""Chỉ giữ bằng chứng của 5 lần chạy gần nhất mỗi case; cũ hơn thì xoá file trên Cloudinary."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.models.media import Media
from app.core.models.run import Evidence, Result, ResultStatus, StepResult
from app.core.services.evidence_retention import KEEP_RESULTS, prune_evidence, results_to_prune

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def shot(name: str) -> Media:
    return Media(
        kind="image", url=f"https://res.cloudinary.com/m/image/upload/{name}.png", public_id=name
    )


def make_result(
    n: int, case: str = "TC-1", evidence: Evidence | None = None, steps: bool = False
) -> Result:
    return Result(
        id=f"RUN-{n:04d}-{case}",
        run_id=f"RUN-{n:04d}",
        test_case_id=case,
        status=ResultStatus.PASS,
        reason="",
        failed_step=None,
        created_at=BASE + timedelta(minutes=n),
        evidence=evidence if evidence is not None else Evidence(screenshots=[shot(f"s{n}")]),
        step_results=[StepResult(step_no=1, status="PASS", screenshot=shot(f"t{n}"))]
        if steps
        else [],
    )


def test_keeps_five_newest_and_prunes_oldest() -> None:
    results = [make_result(n) for n in range(1, 7)]
    pruned = results_to_prune(results, {"TC-1"})
    assert KEEP_RESULTS == 5
    assert [r.id for r in pruned] == ["RUN-0001-TC-1"]


def test_only_listed_cases_are_considered() -> None:
    results = [make_result(n, "TC-1") for n in range(1, 8)] + [make_result(1, "TC-2")]
    assert {r.test_case_id for r in results_to_prune(results, {"TC-2"})} == set()


def test_legacy_url_only_result_is_never_pruned() -> None:
    old = make_result(1, evidence=Evidence(legacy_url="https://example.com/a.png"))
    rest = [make_result(n) for n in range(2, 8)]
    assert old not in results_to_prune([old, *rest], {"TC-1"})


def test_already_pruned_result_is_skipped() -> None:
    old = make_result(1, evidence=Evidence(pruned=True))
    rest = [make_result(n) for n in range(2, 8)]
    assert results_to_prune([old, *rest], {"TC-1"}) == [rest[0]]


class FakeRepo:
    def __init__(self, results: list[Result]) -> None:
        self.results = results
        self.pruned_ids: list[str] = []

    def list_all(self) -> list[Result]:
        return self.results

    def mark_pruned(self, result_ids: list[str]) -> None:
        self.pruned_ids = result_ids


class FakeJanitor:
    def __init__(self, fail: bool = False) -> None:
        self.deleted: list[Media] = []
        self.fail = fail

    def delete(self, items: list[Media]) -> None:
        if self.fail:
            raise RuntimeError("Cloudinary lỗi")
        self.deleted.extend(items)


def test_prune_deletes_every_media_then_marks_pruned() -> None:
    results = [make_result(1, steps=True), *[make_result(n) for n in range(2, 7)]]
    repo, janitor = FakeRepo(results), FakeJanitor()
    prune_evidence(repo, janitor, {"TC-1"})
    assert sorted(m.public_id for m in janitor.deleted) == ["s1", "t1"]
    assert repo.pruned_ids == ["RUN-0001-TC-1"]


def test_janitor_failure_does_not_raise() -> None:
    repo, janitor = FakeRepo([make_result(n) for n in range(1, 7)]), FakeJanitor(fail=True)
    prune_evidence(repo, janitor, {"TC-1"})  # không được ném lỗi
    assert repo.pruned_ids == []


def test_no_janitor_does_nothing() -> None:
    repo = FakeRepo([make_result(n) for n in range(1, 7)])
    prune_evidence(repo, None, {"TC-1"})
    assert repo.pruned_ids == []


@pytest.mark.parametrize("count", [0, 5])
def test_nothing_to_prune(count: int) -> None:
    assert results_to_prune([make_result(n) for n in range(1, count + 1)], {"TC-1"}) == []

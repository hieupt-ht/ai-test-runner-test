import fakeredis

from app.core.run_queue import RunJob, RunQueue


def make_job(run_id: str = "RUN-0001") -> RunJob:
    return RunJob(project_id="PRJ-0001", run_id=run_id, case_ids=["TC-000001", "TC-000002"])


def test_push_pop_is_first_in_first_out(redis: fakeredis.FakeRedis) -> None:
    queue = RunQueue(redis)
    queue.push(make_job("RUN-0001"))
    queue.push(make_job("RUN-0002"))

    first = queue.pop(timeout_seconds=1)
    second = queue.pop(timeout_seconds=1)

    assert first == make_job("RUN-0001")
    assert second == make_job("RUN-0002")


def test_pop_timeout_returns_none(redis: fakeredis.FakeRedis) -> None:
    assert RunQueue(redis).pop(timeout_seconds=1) is None


def test_cancel_flag(redis: fakeredis.FakeRedis) -> None:
    queue = RunQueue(redis)
    assert queue.is_cancelled("PRJ-0001", "RUN-0001") is False

    queue.request_cancel("PRJ-0001", "RUN-0001")

    assert queue.is_cancelled("PRJ-0001", "RUN-0001") is True
    assert queue.is_cancelled("PRJ-0001", "RUN-0002") is False


def test_note_round_trip(redis: fakeredis.FakeRedis) -> None:
    queue = RunQueue(redis)

    queue.set_note("PRJ-0001", "RUN-0001", "Worker bị dừng giữa chừng")

    assert queue.get_note("PRJ-0001", "RUN-0001") == "Worker bị dừng giữa chừng"


def test_note_missing_is_empty(redis: fakeredis.FakeRedis) -> None:
    assert RunQueue(redis).get_note("PRJ-0001", "RUN-0001") == ""


def test_same_run_id_in_two_projects_does_not_share_note_or_cancel_flag(
    redis: fakeredis.FakeRedis,
) -> None:
    """Mã run (RUN-0001) lặp lại ở mọi dự án nên khoá Redis phải kèm mã dự án."""
    queue = RunQueue(redis)

    queue.set_note("PRJ-0001", "RUN-0001", "Lý do của dự án A")
    queue.request_cancel("PRJ-0001", "RUN-0001")

    assert queue.get_note("PRJ-0002", "RUN-0001") == ""
    assert queue.is_cancelled("PRJ-0002", "RUN-0001") is False

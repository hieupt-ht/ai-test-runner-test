import threading

import fakeredis

from app.core.ids import IdGenerator
from app.core.sheets.schema import META_TAB, PROJECT_TABS
from tests.fakes import FakeSheetsGateway

SHEET = "project-sheet"


def make_generator() -> tuple[IdGenerator, FakeSheetsGateway]:
    gateway = FakeSheetsGateway({SHEET: {META_TAB: [list(PROJECT_TABS[META_TAB])]}})
    return IdGenerator(gateway, SHEET, fakeredis.FakeRedis(), "PRJ-0001"), gateway


def test_first_and_next_ids() -> None:
    ids, gateway = make_generator()

    assert ids.next_id("screen", "SC") == "SC-0001"
    assert ids.next_id("screen", "SC") == "SC-0002"
    assert ["next_screen_id", "3"] in gateway.data[SHEET][META_TAB]


def test_counters_are_separate_per_entity() -> None:
    ids, _ = make_generator()

    assert ids.next_id("screen", "SC") == "SC-0001"
    assert ids.next_id("assignment", "AS") == "AS-0001"


def test_two_threads_never_get_same_id() -> None:
    ids, _ = make_generator()
    results: list[str] = []
    guard = threading.Lock()

    def worker() -> None:
        for _ in range(10):
            new_id = ids.next_id("screen", "SC")
            with guard:
                results.append(new_id)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(set(results)) == 20

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from multiprocessing import get_context

from intent_integrity import ActionAlreadyClaimed, EventType, SQLiteEventStore, TaskEvent


def _append_events(database: str, worker_id: int, count: int) -> int:
    with SQLiteEventStore(database) as store:
        for index in range(count):
            store.append_event(
                TaskEvent(
                    task_id="shared-task",
                    event_type=EventType.PLAN_RECORDED,
                    payload={"worker": worker_id, "index": index},
                    occurred_at=datetime.now(UTC),
                    event_id=f"worker-{worker_id}-event-{index}",
                )
            )
    return count


def _claim_once(database: str) -> str:
    with SQLiteEventStore(database) as store:
        try:
            store.claim_action(
                "shared-task",
                "one-action",
                "write_report",
                datetime.now(UTC),
            )
        except ActionAlreadyClaimed:
            return "duplicate"
        return "claimed"


def test_parallel_processes_append_contiguous_verified_event_chain(tmp_path) -> None:
    database = str(tmp_path / "concurrent.sqlite3")
    with SQLiteEventStore(database):
        pass
    workers = 4
    events_per_worker = 8
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
        results = list(
            pool.map(
                _append_events,
                [database] * workers,
                list(range(workers)),
                [events_per_worker] * workers,
            )
        )
    assert sum(results) == workers * events_per_worker
    with SQLiteEventStore(database) as store:
        events = store.list_events("shared-task")
        assert len(events) == workers * events_per_worker
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        assert store.verify_event_chain("shared-task")


def test_parallel_processes_cannot_claim_the_same_action_twice(tmp_path) -> None:
    database = str(tmp_path / "claims.sqlite3")
    with SQLiteEventStore(database):
        pass
    with ProcessPoolExecutor(max_workers=6, mp_context=get_context("spawn")) as pool:
        outcomes = list(pool.map(_claim_once, [database] * 6))
    assert outcomes.count("claimed") == 1
    assert outcomes.count("duplicate") == 5
    with SQLiteEventStore(database) as store:
        assert store.get_action_record("shared-task", "one-action") is not None

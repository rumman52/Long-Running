from datetime import UTC, datetime

import pytest

from intent_integrity import (
    ActionAlreadyClaimed,
    ActionStatus,
    DuplicateEventConflict,
    EventIntegrityError,
    EventType,
    SQLiteEventStore,
    TaskEvent,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def make_event(*, event_id: str = "event-1", payload: dict[str, object] | None = None) -> TaskEvent:
    return TaskEvent(
        task_id="task-1",
        event_id=event_id,
        event_type=EventType.TASK_STARTED,
        occurred_at=NOW,
        payload=payload or {"goal": "prepare a report"},
    )


def test_event_append_is_ordered_and_idempotent(tmp_path) -> None:
    with SQLiteEventStore(tmp_path / "events.sqlite3") as store:
        first = store.append_event(make_event())
        retry = store.append_event(make_event())
        second = store.append_event(
            TaskEvent("task-1", EventType.PLAN_RECORDED, {"steps": 2}, NOW, "event-2")
        )
        assert first.sequence == retry.sequence == 1
        assert second.sequence == 2
        assert store.verify_event_chain("task-1")
        assert [item.sequence for item in store.list_events("task-1")] == [1, 2]


def test_reusing_event_id_with_different_content_fails(tmp_path) -> None:
    with SQLiteEventStore(tmp_path / "events.sqlite3") as store:
        store.append_event(make_event())
        with pytest.raises(DuplicateEventConflict):
            store.append_event(make_event(payload={"goal": "different goal"}))


def test_event_chain_detects_modified_event_hash(tmp_path) -> None:
    with SQLiteEventStore(tmp_path / "events.sqlite3") as store:
        store.append_event(make_event())
        store._connection.execute(
            "UPDATE events SET event_hash = ? WHERE task_id = ? AND sequence = ?",
            ("0" * 64, "task-1", 1),
        )
        assert not store.verify_event_chain("task-1")


def test_checkpoint_state_hash_is_verified(tmp_path) -> None:
    with SQLiteEventStore(tmp_path / "events.sqlite3") as store:
        checkpoint = store.save_checkpoint("task-1", {"goal": "preserve intent"})
        loaded = store.load_latest_checkpoint("task-1")
        assert loaded is not None
        assert loaded.checkpoint_id == checkpoint.checkpoint_id
        assert loaded.state == {"goal": "preserve intent"}
        store._connection.execute(
            "UPDATE checkpoints SET state_json = ? WHERE checkpoint_id = ?",
            ('{"goal":"tampered"}', checkpoint.checkpoint_id),
        )
        with pytest.raises(EventIntegrityError):
            store.load_latest_checkpoint("task-1")


def test_action_claim_cannot_be_reused(tmp_path) -> None:
    with SQLiteEventStore(tmp_path / "events.sqlite3") as store:
        store.claim_action("task-1", "action-1", "publish", NOW)
        store.finish_action(
            "task-1", "action-1", ActionStatus.SUCCEEDED, {"result_type": "str"}
        )
        record = store.get_action_record("task-1", "action-1")
        assert record is not None
        assert record.status == ActionStatus.SUCCEEDED
        with pytest.raises(ActionAlreadyClaimed):
            store.claim_action("task-1", "action-1", "publish", NOW)


def test_claimed_action_can_be_marked_unknown_but_not_reset(tmp_path) -> None:
    with SQLiteEventStore(tmp_path / "events.sqlite3") as store:
        store.claim_action("task-1", "action-1", "publish", NOW)
        store.finish_action(
            "task-1", "action-1", ActionStatus.UNKNOWN, {"error_type": "TimeoutError"}
        )
        record = store.get_action_record("task-1", "action-1")
        assert record is not None
        assert record.status == ActionStatus.UNKNOWN
        with pytest.raises(ActionAlreadyClaimed):
            store.claim_action("task-1", "action-1", "publish", NOW)

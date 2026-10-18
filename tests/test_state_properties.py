from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings, strategies as st

from intent_integrity import (
    ActionAlreadyClaimed,
    ActionStateError,
    ActionStatus,
    EventType,
    SQLiteEventStore,
    TaskEvent,
)


@given(st.lists(st.text(max_size=80), min_size=0, max_size=30))
@settings(max_examples=60, deadline=None)
def test_generated_event_sequences_keep_valid_hash_chains(payloads: list[str]) -> None:
    with SQLiteEventStore(":memory:") as store:
        for index, payload in enumerate(payloads):
            store.append_event(
                TaskEvent(
                    task_id="generated-task",
                    event_type=EventType.PLAN_RECORDED,
                    payload={"index": index, "text": payload},
                    occurred_at=datetime(2026, 10, 18, tzinfo=UTC),
                    event_id=f"event-{index}",
                )
            )
        stored = store.list_events("generated-task")
        assert [event.sequence for event in stored] == list(range(1, len(payloads) + 1))
        assert store.verify_event_chain("generated-task")


@given(
    st.sampled_from([ActionStatus.SUCCEEDED, ActionStatus.UNKNOWN]),
    st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=st.one_of(st.text(max_size=20), st.integers(), st.booleans(), st.none()),
        max_size=5,
    ),
)
@settings(max_examples=40, deadline=None)
def test_generated_terminal_action_states_cannot_transition(
    initial: ActionStatus, result: dict[str, object]
) -> None:
    with SQLiteEventStore(":memory:") as store:
        store.claim_action("state-task", "action-1", "write_report", datetime.now(UTC))
        store.finish_action("state-task", "action-1", initial, result)
        store.finish_action("state-task", "action-1", initial, result)
        other = (
            ActionStatus.UNKNOWN
            if initial == ActionStatus.SUCCEEDED
            else ActionStatus.SUCCEEDED
        )
        with pytest.raises(ActionStateError):
            store.finish_action("state-task", "action-1", other, result)


@given(st.text(min_size=1, max_size=40))
@settings(max_examples=30, deadline=None)
def test_generated_duplicate_claims_fail_closed(action_id: str) -> None:
    with SQLiteEventStore(":memory:") as store:
        store.claim_action("claim-task", action_id, "write_report", datetime.now(UTC))
        with pytest.raises(ActionAlreadyClaimed):
            store.claim_action("claim-task", action_id, "write_report", datetime.now(UTC))

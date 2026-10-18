"""Versioned runtime events and durable record types.

Events are facts about a run, not instructions or authorization. Their payloads must never
override the active intent contract or trusted host policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import uuid4


class EventType(StrEnum):
    """Supported events emitted by the first runtime implementation."""

    TASK_STARTED = "TASK_STARTED"
    PLAN_RECORDED = "PLAN_RECORDED"
    STEP_COMPLETED = "STEP_COMPLETED"
    ASSUMPTION_INVALIDATED = "ASSUMPTION_INVALIDATED"
    EVIDENCE_REFRESHED = "EVIDENCE_REFRESHED"
    APPROVAL_CHANGED = "APPROVAL_CHANGED"
    ACTION_VALIDATED = "ACTION_VALIDATED"
    ACTION_CLAIMED = "ACTION_CLAIMED"
    ACTION_SUCCEEDED = "ACTION_SUCCEEDED"
    ACTION_OUTCOME_UNKNOWN = "ACTION_OUTCOME_UNKNOWN"
    CONTRACT_AMENDED = "CONTRACT_AMENDED"
    CHECKPOINT_SAVED = "CHECKPOINT_SAVED"
    TASK_COMPLETED = "TASK_COMPLETED"


class ActionStatus(StrEnum):
    """Durable execution states. CLAIMED and UNKNOWN are never safe to retry blindly."""

    CLAIMED = "CLAIMED"
    SUCCEEDED = "SUCCEEDED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class TaskEvent:
    """An append-only event submitted to the event ledger."""

    task_id: str
    event_type: EventType
    payload: dict[str, object] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    event_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not self.event_id.strip():
            raise ValueError("event_id must be a non-empty string")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        try:
            json.dumps(self.payload, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("event payload must be JSON-serializable") from exc


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """A persisted event with sequence and hash-chain metadata."""

    event: TaskEvent
    sequence: int
    previous_hash: str
    event_hash: str


@dataclass(frozen=True, slots=True)
class CheckpointRecord:
    """A persisted snapshot tied to an event sequence."""

    checkpoint_id: str
    task_id: str
    sequence: int
    created_at: datetime
    state: dict[str, object]
    state_hash: str


@dataclass(frozen=True, slots=True)
class ActionRecord:
    """Durable idempotency record for a proposed action."""

    task_id: str
    action_id: str
    category: str
    status: ActionStatus
    claimed_at: datetime
    result: dict[str, object] | None = None

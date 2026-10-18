"""SQLite-backed event history, checkpoints, and fail-closed action claims."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from intent_integrity.events import (
    ActionRecord,
    ActionStatus,
    CheckpointRecord,
    EventType,
    StoredEvent,
    TaskEvent,
)

_ZERO_HASH = "0" * 64


class EventStoreError(RuntimeError):
    """Base error for durable store failures."""


class DuplicateEventConflict(EventStoreError):
    """An event ID was reused with different event content."""


class EventIntegrityError(EventStoreError):
    """The event chain or a stored checkpoint failed integrity verification."""


class ActionAlreadyClaimed(EventStoreError):
    """An action ID has already been claimed and must not execute again."""


class ActionStateError(EventStoreError):
    """An action execution record attempted an invalid state transition."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _event_envelope(event: TaskEvent, sequence: int, previous_hash: str) -> dict[str, object]:
    return {
        "task_id": event.task_id,
        "sequence": sequence,
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
        "previous_hash": previous_hash,
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SQLiteEventStore:
    """Small persistence adapter using only the Python standard library.

    The ledger uses a per-task sequence and SHA-256 hash chain to make accidental or
    unauthorized edits detectable. This is tamper-evident, not tamper-proof: an attacker
    who can rewrite the entire database can also recompute the chain.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            self.path, timeout=10, check_same_thread=False, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 10000")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    task_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    PRIMARY KEY (task_id, sequence),
                    UNIQUE (task_id, event_id)
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    state_hash TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS checkpoints_latest
                ON checkpoints(task_id, sequence DESC, created_at DESC);

                CREATE TABLE IF NOT EXISTS action_claims (
                    task_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    result_json TEXT,
                    PRIMARY KEY (task_id, action_id)
                );
                """
            )

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteEventStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> StoredEvent:
        envelope = json.loads(str(row["envelope_json"]))
        payload = envelope["payload"]
        if not isinstance(payload, dict):
            raise EventIntegrityError("Stored event payload is not a JSON object")
        event = TaskEvent(
            task_id=str(envelope["task_id"]),
            event_id=str(envelope["event_id"]),
            event_type=EventType(str(envelope["event_type"])),
            occurred_at=datetime.fromisoformat(str(envelope["occurred_at"])),
            payload=payload,
        )
        return StoredEvent(
            event=event,
            sequence=int(envelope["sequence"]),
            previous_hash=str(row["previous_hash"]),
            event_hash=str(row["event_hash"]),
        )

    def append_event(self, event: TaskEvent) -> StoredEvent:
        """Append once; identical retries are idempotent and conflicting retries fail."""
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self._connection.execute(
                    "SELECT * FROM events WHERE task_id = ? AND event_id = ?",
                    (event.task_id, event.event_id),
                ).fetchone()
                if existing is not None:
                    stored = self._row_to_event(existing)
                    same_event = (
                        stored.event.event_type == event.event_type
                        and stored.event.occurred_at == event.occurred_at
                        and stored.event.payload == event.payload
                    )
                    if not same_event:
                        raise DuplicateEventConflict(
                            "event_id was already used with different event content"
                        )
                    self._connection.execute("COMMIT")
                    return stored

                latest = self._connection.execute(
                    "SELECT sequence, event_hash FROM events "
                    "WHERE task_id = ? ORDER BY sequence DESC LIMIT 1",
                    (event.task_id,),
                ).fetchone()
                sequence = int(latest["sequence"]) + 1 if latest else 1
                previous_hash = str(latest["event_hash"]) if latest else _ZERO_HASH
                envelope_json = _canonical_json(
                    _event_envelope(event, sequence, previous_hash)
                )
                event_hash = _sha256(envelope_json)
                self._connection.execute(
                    """
                    INSERT INTO events (
                        task_id, sequence, event_id, event_type, occurred_at,
                        payload_json, previous_hash, event_hash, envelope_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.task_id,
                        sequence,
                        event.event_id,
                        event.event_type.value,
                        event.occurred_at.isoformat(),
                        _canonical_json(event.payload),
                        previous_hash,
                        event_hash,
                        envelope_json,
                    ),
                )
                self._connection.execute("COMMIT")
                return StoredEvent(event, sequence, previous_hash, event_hash)
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def list_events(self, task_id: str, *, after_sequence: int = 0) -> tuple[StoredEvent, ...]:
        """Return a task's events in durable sequence order."""
        if after_sequence < 0:
            raise ValueError("after_sequence must be zero or greater")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM events WHERE task_id = ? AND sequence > ? ORDER BY sequence",
                (task_id, after_sequence),
            ).fetchall()
        return tuple(self._row_to_event(row) for row in rows)

    def verify_event_chain(self, task_id: str) -> bool:
        """Verify contiguous sequence numbers, previous hashes, and event hashes."""
        previous_hash = _ZERO_HASH
        expected_sequence = 1
        for stored in self.list_events(task_id):
            if stored.sequence != expected_sequence or stored.previous_hash != previous_hash:
                return False
            envelope_json = _canonical_json(
                _event_envelope(stored.event, stored.sequence, stored.previous_hash)
            )
            if _sha256(envelope_json) != stored.event_hash:
                return False
            previous_hash = stored.event_hash
            expected_sequence += 1
        return True

    def save_checkpoint(self, task_id: str, state: Mapping[str, object]) -> CheckpointRecord:
        """Persist a JSON-compatible snapshot at the current event sequence."""
        if not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        state_json = _canonical_json(dict(state))
        state_hash = _sha256(state_json)
        checkpoint_id = str(uuid4())
        created_at = datetime.now(UTC)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                latest = self._connection.execute(
                    "SELECT sequence FROM events WHERE task_id = ? "
                    "ORDER BY sequence DESC LIMIT 1",
                    (task_id,),
                ).fetchone()
                sequence = int(latest["sequence"]) if latest else 0
                self._connection.execute(
                    """
                    INSERT INTO checkpoints (
                        checkpoint_id, task_id, sequence, created_at, state_json, state_hash
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        checkpoint_id,
                        task_id,
                        sequence,
                        created_at.isoformat(),
                        state_json,
                        state_hash,
                    ),
                )
                self._connection.execute("COMMIT")
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
        return CheckpointRecord(
            checkpoint_id, task_id, sequence, created_at, dict(state), state_hash
        )

    def load_latest_checkpoint(self, task_id: str) -> CheckpointRecord | None:
        """Load the newest checkpoint and reject a corrupted state payload."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM checkpoints WHERE task_id = ? "
                "ORDER BY sequence DESC, created_at DESC LIMIT 1",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        state_json = str(row["state_json"])
        if _sha256(state_json) != str(row["state_hash"]):
            raise EventIntegrityError("Checkpoint state hash verification failed")
        state: Any = json.loads(state_json)
        if not isinstance(state, dict):
            raise EventIntegrityError("Checkpoint state is not a JSON object")
        return CheckpointRecord(
            checkpoint_id=str(row["checkpoint_id"]),
            task_id=str(row["task_id"]),
            sequence=int(row["sequence"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            state=state,
            state_hash=str(row["state_hash"]),
        )

    def claim_action(
        self,
        task_id: str,
        action_id: str,
        category: str,
        claimed_at: datetime,
    ) -> None:
        """Claim an action ID before execution; every existing claim fails closed."""
        if claimed_at.tzinfo is None or claimed_at.utcoffset() is None:
            raise ValueError("claimed_at must be timezone-aware")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self._connection.execute(
                    "SELECT status FROM action_claims WHERE task_id = ? AND action_id = ?",
                    (task_id, action_id),
                ).fetchone()
                if existing is not None:
                    raise ActionAlreadyClaimed(
                        f"Action {action_id!r} already exists with state {existing['status']}"
                    )
                self._connection.execute(
                    """
                    INSERT INTO action_claims (
                        task_id, action_id, category, status, claimed_at, result_json
                    ) VALUES (?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        task_id,
                        action_id,
                        category,
                        ActionStatus.CLAIMED.value,
                        claimed_at.isoformat(),
                    ),
                )
                self._connection.execute("COMMIT")
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def finish_action(
        self,
        task_id: str,
        action_id: str,
        status: ActionStatus,
        result: Mapping[str, object],
    ) -> None:
        """Finalize a claim as SUCCEEDED or UNKNOWN; claims cannot be reset for retry."""
        if status not in (ActionStatus.SUCCEEDED, ActionStatus.UNKNOWN):
            raise ValueError("final action status must be SUCCEEDED or UNKNOWN")
        result_json = _canonical_json(dict(result))
        with self._lock:
            row = self._connection.execute(
                "SELECT status, result_json FROM action_claims "
                "WHERE task_id = ? AND action_id = ?",
                (task_id, action_id),
            ).fetchone()
            if row is None:
                raise ActionStateError("Cannot finalize an action that was never claimed")
            current_status = ActionStatus(str(row["status"]))
            if current_status != ActionStatus.CLAIMED:
                if current_status == status and row["result_json"] == result_json:
                    return
                raise ActionStateError(
                    f"Cannot transition action from {current_status.value} to {status.value}"
                )
            self._connection.execute(
                "UPDATE action_claims SET status = ?, result_json = ? "
                "WHERE task_id = ? AND action_id = ?",
                (status.value, result_json, task_id, action_id),
            )

    def get_action_record(self, task_id: str, action_id: str) -> ActionRecord | None:
        """Read an action claim without allowing it to be reset."""
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM action_claims WHERE task_id = ? AND action_id = ?",
                (task_id, action_id),
            ).fetchone()
        if row is None:
            return None
        raw_result = row["result_json"]
        result: dict[str, object] | None = None
        if raw_result is not None:
            parsed: Any = json.loads(str(raw_result))
            if isinstance(parsed, dict):
                result = parsed
        return ActionRecord(
            task_id=str(row["task_id"]),
            action_id=str(row["action_id"]),
            category=str(row["category"]),
            status=ActionStatus(str(row["status"])),
            claimed_at=datetime.fromisoformat(str(row["claimed_at"])),
            result=result,
        )

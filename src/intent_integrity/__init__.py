"""Intent Integrity: trusted intent preservation for long-running AI tasks."""

from intent_integrity.drift import (
    DriftReport,
    DriftSeverity,
    DriftSignal,
    PlanStep,
    detect_plan_drift,
)
from intent_integrity.engine import (
    ActionExecutionOutcome,
    CheckpointState,
    IntentIntegrityEngine,
    RecoveryBundle,
    build_compact_context,
)
from intent_integrity.events import (
    ActionRecord,
    ActionStatus,
    CheckpointRecord,
    EventType,
    StoredEvent,
    TaskEvent,
)
from intent_integrity.models import (
    ActionRequest,
    Approval,
    ApprovalStatus,
    Assumption,
    Decision,
    Evidence,
    IntentContract,
    ValidationContext,
    ValidationResult,
)
from intent_integrity.serialization import contract_from_dict, contract_to_dict
from intent_integrity.store import (
    ActionAlreadyClaimed,
    ActionStateError,
    DuplicateEventConflict,
    EventIntegrityError,
    EventStoreError,
    SQLiteEventStore,
)
from intent_integrity.validator import validate_action

__all__ = [
    "ActionAlreadyClaimed",
    "ActionExecutionOutcome",
    "ActionRecord",
    "ActionRequest",
    "ActionStateError",
    "ActionStatus",
    "Approval",
    "ApprovalStatus",
    "Assumption",
    "CheckpointRecord",
    "CheckpointState",
    "Decision",
    "DriftReport",
    "DriftSeverity",
    "DriftSignal",
    "DuplicateEventConflict",
    "EventIntegrityError",
    "EventStoreError",
    "EventType",
    "Evidence",
    "IntentContract",
    "IntentIntegrityEngine",
    "PlanStep",
    "RecoveryBundle",
    "SQLiteEventStore",
    "StoredEvent",
    "TaskEvent",
    "ValidationContext",
    "ValidationResult",
    "build_compact_context",
    "contract_from_dict",
    "contract_to_dict",
    "detect_plan_drift",
    "validate_action",
]

"""Intent Integrity: trusted intent preservation for long-running AI tasks."""

from intent_integrity.adapter import GuardedToolAdapter, ToolCallResult, ToolDefinition
from intent_integrity.drift import (
    DriftReport, DriftSeverity, DriftSignal, PlanStep, detect_plan_drift,
)
from intent_integrity.engine import (
    ActionExecutionOutcome, CheckpointState, CompletionReport,
    IntentIntegrityEngine, RecoveryBundle,
    build_compact_context,
)
from intent_integrity.events import (
    ActionRecord, ActionStatus, CheckpointRecord, EventType, ExternalActionRecord,
    StoredEvent, TaskEvent,
)
from intent_integrity.mcp_server import MCPStdioServer
from intent_integrity.models import (
    ActionRequest, Approval, ApprovalStatus, Assumption, Decision, Evidence, IntentContract,
    ValidationContext, ValidationResult,
)
from intent_integrity.serialization import contract_from_dict, contract_to_dict
from intent_integrity.store import (
    ActionAlreadyClaimed, ActionStateError, DuplicateEventConflict, EventIntegrityError,
    EventStoreError, SQLiteEventStore,
)
from intent_integrity.reconciliation import (
    ExternalActionCoordinator, ExternalExecutionResult, ExternalOperation, OutcomeStatus,
    ProviderOutcome, ProviderRequest, ReconciliationProvider,
)
from intent_integrity.semantic import (
    GemmaOllamaProvider, ProviderResponse, SemanticAssessment, SemanticComparisonRequest,
    SemanticDriftProvider, SemanticDriftResult, SemanticFinding, SemanticSeverity, SemanticStatus,
    analyze_semantic_drift,
)
from intent_integrity.validator import validate_action

__all__ = [
    "ExternalActionCoordinator", "ExternalActionRecord", "ExternalExecutionResult",
    "ExternalOperation", "OutcomeStatus", "ProviderOutcome", "ProviderRequest",
    "ReconciliationProvider", "GemmaOllamaProvider", "ProviderResponse", "SemanticAssessment",
    "SemanticComparisonRequest", "SemanticDriftProvider", "SemanticDriftResult", "SemanticFinding",
    "SemanticSeverity", "SemanticStatus", "analyze_semantic_drift",
    "ActionAlreadyClaimed", "ActionExecutionOutcome", "ActionRecord", "ActionRequest",
    "ActionStateError", "ActionStatus", "Approval", "ApprovalStatus", "Assumption",
    "CheckpointRecord", "CheckpointState", "CompletionReport", "Decision",
    "DriftReport", "DriftSeverity",
    "DriftSignal", "DuplicateEventConflict", "EventIntegrityError", "EventStoreError",
    "EventType", "Evidence", "GuardedToolAdapter", "IntentContract", "IntentIntegrityEngine",
    "MCPStdioServer", "PlanStep", "RecoveryBundle", "SQLiteEventStore", "StoredEvent",
    "TaskEvent", "ToolCallResult", "ToolDefinition", "ValidationContext", "ValidationResult",
    "build_compact_context", "contract_from_dict", "contract_to_dict", "detect_plan_drift",
    "validate_action",
]

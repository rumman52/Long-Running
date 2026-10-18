"""Provider-neutral recovery of external actions with explicitly guarded retries."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from intent_integrity.engine import IntentIntegrityEngine
from intent_integrity.events import ActionStatus, ExternalActionRecord
from intent_integrity.models import (
    ActionRequest, Decision, IntentContract, ValidationContext, ValidationResult,
)
from intent_integrity.store import ActionStateError, EventIntegrityError


class OutcomeStatus(StrEnum):
    """Provider observations. NOT_APPLIED must be authoritative, not eventual absence."""

    SUCCEEDED = "SUCCEEDED"
    NOT_APPLIED = "NOT_APPLIED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ProviderOutcome:
    """A trusted provider's observation, never a model-supplied completion claim."""

    status: OutcomeStatus
    provider_reference: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, OutcomeStatus):
            raise ValueError("Provider outcome requires a known OutcomeStatus")
        if self.provider_reference is not None and (
            not isinstance(self.provider_reference, str) or not self.provider_reference.strip()
        ):
            raise ValueError("provider_reference must be a non-empty string")
        if self.status == OutcomeStatus.SUCCEEDED and self.provider_reference is None:
            raise ValueError("Success requires a provider receipt/reference")
        if self.detail is not None and not isinstance(self.detail, str):
            raise ValueError("Provider detail must be a string")

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status.value, "provider_reference": self.provider_reference,
                "detail": self.detail}


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Operation identifiers must be non-empty strings")
    return value


def _payload_copy(payload: dict[str, object]) -> dict[str, object]:
    def check(value: object) -> None:
        if isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("Provider payload keys must be strings")
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
        elif value is not None and type(value) not in (str, bool, int, float):
            raise ValueError("Provider payload must contain JSON values")
    if not isinstance(payload, dict):
        raise ValueError("Provider payload must be a JSON object")
    check(payload)
    copied: dict[str, object] = json.loads(json.dumps(payload, allow_nan=False))
    return copied


@dataclass(frozen=True, slots=True)
class ExternalOperation:
    """Host-owned logical operation; keep operation_id stable for the intended effect."""

    provider_id: str
    operation_id: str
    payload: dict[str, object]
    expected_version: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.provider_id)
        _identifier(self.operation_id)
        _payload_copy(self.payload)
        if self.expected_version is not None:
            _identifier(self.expected_version)


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    """Persisted request delivered unchanged on every attempt and outcome lookup."""

    provider_id: str
    operation_id: str
    payload: dict[str, object]
    expected_version: str | None
    idempotency_key: str
    idempotency_expires_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id, "operation_id": self.operation_id,
            "payload": _payload_copy(self.payload), "expected_version": self.expected_version,
            "idempotency_key": self.idempotency_key,
            "idempotency_expires_at": self.idempotency_expires_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: ExternalActionRecord) -> ProviderRequest:
        raw = record.operation
        payload = raw.get("payload")
        if not isinstance(payload, dict):
            raise EventIntegrityError("Stored provider payload is malformed")
        version = raw.get("expected_version")
        if version is not None:
            _identifier(version)
        expiry = datetime.fromisoformat(_identifier(raw.get("idempotency_expires_at")))
        if expiry.tzinfo is None or expiry.utcoffset() is None:
            raise EventIntegrityError("Stored idempotency deadline lacks timezone")
        return cls(_identifier(raw.get("provider_id")), _identifier(raw.get("operation_id")),
                   _payload_copy(payload), version if isinstance(version, str) else None,
                   _identifier(raw.get("idempotency_key")), expiry)


class ReconciliationProvider(Protocol):
    """Trusted adapter contract; guarantees must hold at the actual external write boundary.

    Execute atomically deduplicates the key, binds its payload and expected_version, checks
    the resource version, and rejects requests past idempotency_expires_at before effects.
    Lookup never writes. NOT_APPLIED/REJECTED mean a definitive outcome, not a 404 from an
    eventually consistent listing. Unsupported capabilities must not be advertised.
    """

    provider_id: str
    idempotency_ttl_seconds: int

    def execute(self, request: ProviderRequest) -> ProviderOutcome: ...

    def lookup(self, request: ProviderRequest) -> ProviderOutcome: ...


@dataclass(frozen=True, slots=True)
class ExternalExecutionResult:
    """Validation and durable result of an initial submission or explicit retry."""

    validation: ValidationResult
    record: ExternalActionRecord | None
    submitted: bool


class ExternalActionCoordinator:
    """Coordinate trusted authorization, durable operation identities, and provider recovery."""

    def __init__(self, engine: IntentIntegrityEngine,
                 providers: Iterable[ReconciliationProvider], *,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.engine = engine
        self.store = engine.store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._providers: dict[str, ReconciliationProvider] = {}
        for provider in providers:
            _identifier(provider.provider_id)
            if (type(provider.idempotency_ttl_seconds) is not int
                or provider.idempotency_ttl_seconds <= 0):
                raise ValueError("Provider must guarantee a positive idempotency retention window")
            if provider.provider_id in self._providers:
                raise ValueError("Duplicate provider identity")
            self._providers[provider.provider_id] = provider

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Coordinator clock must be timezone-aware")
        return now

    def _provider(self, provider_id: str) -> ReconciliationProvider:
        if provider_id not in self._providers:
            raise ActionStateError("Trusted provider is unavailable; no operation was submitted")
        return self._providers[provider_id]

    def _record(self, contract: IntentContract, action_id: str) -> ExternalActionRecord:
        self.engine._require_active_contract(contract)
        record = self.store.get_external_action(contract.contract_id, action_id)
        if record is None:
            raise ActionStateError("No provider-aware action claim exists")
        return record

    def _observe(self, record: ExternalActionRecord, *, lookup: bool) -> ExternalActionRecord:
        request = ProviderRequest.from_record(record)
        provider = self._provider(request.provider_id)
        try:
            outcome = provider.lookup(request) if lookup else provider.execute(request)
            if not isinstance(outcome, ProviderOutcome):
                raise ValueError("Malformed provider response")
            # Revalidate even if a trusted adapter mutated a frozen object indirectly.
            outcome = ProviderOutcome(outcome.status, outcome.provider_reference, outcome.detail)
        except Exception as exc:
            outcome = ProviderOutcome(OutcomeStatus.UNKNOWN, detail=type(exc).__name__)
        status = {
            OutcomeStatus.SUCCEEDED: ActionStatus.SUCCEEDED,
            OutcomeStatus.NOT_APPLIED: ActionStatus.NOT_APPLIED,
            OutcomeStatus.REJECTED: ActionStatus.REJECTED,
            OutcomeStatus.PENDING: ActionStatus.UNKNOWN,
            OutcomeStatus.UNKNOWN: ActionStatus.UNKNOWN,
        }[outcome.status]
        try:
            return self.store.transition_external_action(
                record.action.task_id, record.action.action_id, record.revision,
                status, outcome.to_dict(), self._now(),
            )
        except ActionStateError:
            # A concurrent observer/attempt won; never overwrite its newer state.
            latest = self.store.get_external_action(record.action.task_id, record.action.action_id)
            if latest is None:
                raise
            return latest

    def execute(
        self, contract: IntentContract, action: ActionRequest,
        context: ValidationContext, operation: ExternalOperation,
    ) -> ExternalExecutionResult:
        """Validate and durably claim the logical effect before contacting its provider."""
        now = self._now()
        validation = self.engine.validate_action(contract, action, replace(context, now=now))
        if validation.decision != Decision.ALLOW:
            return ExternalExecutionResult(validation, None, False)
        provider = self._provider(operation.provider_id)
        key_data = json.dumps([operation.provider_id, operation.operation_id]).encode()
        request = ProviderRequest(
            operation.provider_id, operation.operation_id, _payload_copy(operation.payload),
            operation.expected_version, "ii-" + hashlib.sha256(key_data).hexdigest(),
            now + timedelta(seconds=provider.idempotency_ttl_seconds),
        )
        metadata = request.to_dict()
        metadata["contract_version"] = contract.version
        record = self.store.claim_external_action(
            contract.contract_id, action.action_id, action.category, metadata, now,
        )
        return ExternalExecutionResult(validation, self._observe(record, lookup=False), True)

    def reconcile(self, contract: IntentContract, action_id: str) -> ExternalActionRecord:
        """Refresh a nonterminal outcome without submitting an external write."""
        record = self._record(contract, action_id)
        if record.action.status in (ActionStatus.SUCCEEDED, ActionStatus.REJECTED):
            return record
        return self._observe(record, lookup=True)

    def reconcile_pending(self, contract: IntentContract) -> tuple[ExternalActionRecord, ...]:
        """Reconcile ambiguous provider-aware claims after a restart without resubmitting."""
        self.engine._require_active_contract(contract)
        return tuple(self.reconcile(contract, record.action.action_id)
                     for record in self.store.list_external_actions(contract.contract_id)
                     if record.action.status not in (ActionStatus.SUCCEEDED, ActionStatus.REJECTED))

    def retry(self, contract: IntentContract, action_id: str,
              context: ValidationContext) -> ExternalExecutionResult:
        """Resubmit a proven absent effect with fresh authorization and the original key."""
        record = self._record(contract, action_id)
        if record.action.status != ActionStatus.NOT_APPLIED:
            raise ActionStateError("Retry requires authoritative NOT_APPLIED state")
        now = self._now()
        request = ProviderRequest.from_record(record)
        if now >= request.idempotency_expires_at:
            raise ActionStateError("Provider idempotency window expired")
        if record.operation.get("contract_version") != contract.version:
            raise ActionStateError("Original contract version changed; retry requires intervention")
        self._provider(request.provider_id)
        action = ActionRequest(record.action.action_id, record.action.category)
        validation = self.engine.validate_action(contract, action, replace(context, now=now))
        if validation.decision != Decision.ALLOW:
            return ExternalExecutionResult(validation, record, False)
        claimed = self.store.transition_external_action(
            contract.contract_id, action_id, record.revision, ActionStatus.CLAIMED,
            {"status": "RETRY_CLAIMED"}, self._now(), retry=True,
        )
        return ExternalExecutionResult(validation, self._observe(claimed, lookup=False), True)

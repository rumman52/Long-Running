"""Typed, framework-neutral data models for intent integrity validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Decision(StrEnum):
    """Decision returned by the deterministic pre-action validator."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"


class ApprovalStatus(StrEnum):
    """Known approval states. Missing approvals are represented by absence from the context."""

    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class Assumption:
    """An assumption a plan depends on, with explicit invalidation conditions."""

    assumption_id: str
    statement: str
    evidence_ids: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IntentContract:
    """Versioned policy derived from the user's intent and accepted by the host.

    Action requirements are contract-owned rather than supplied by the model with each action.
    Natural-language constraints and acceptance criteria are declarations; they are not
    automatically enforced unless mapped to machine-checkable rules.
    """

    contract_id: str
    version: int
    goal: str
    constraints: tuple[str, ...] = ()
    permitted_actions: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    consequential_actions: tuple[str, ...] = ()
    required_evidence_by_action: tuple[tuple[str, tuple[str, ...]], ...] = ()
    required_approvals_by_action: tuple[tuple[str, tuple[str, ...]], ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    required_approvals: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Evidence:
    """Evidence about a resource.

    observed_version/current_version should be populated for versioned resources such as
    files, branches, records, or documents. If a resource is versioned but its current version
    cannot be obtained, validation requires revalidation rather than assuming it is unchanged.
    """

    evidence_id: str
    source: str
    observed_at: datetime | None
    resource_id: str | None = None
    observed_version: str | None = None
    current_version: str | None = None
    freshness_ttl_seconds: int | None = None
    invalidated: bool = False
    verified: bool = True


@dataclass(frozen=True, slots=True)
class Approval:
    """An approval record scoped to action categories."""

    approval_id: str
    status: ApprovalStatus
    expires_at: datetime | None = None
    allowed_actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """A proposed action. Requirements are resolved from trusted contract policy."""

    action_id: str
    category: str


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Current trusted observations supplied by the integration adapter."""

    now: datetime
    evidence: dict[str, Evidence] = field(default_factory=dict)
    approvals: dict[str, Approval] = field(default_factory=dict)
    active_contract_version: int | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Structured decision and audit details from a validation attempt."""

    decision: Decision
    reason_codes: tuple[str, ...]
    details: tuple[str, ...]
    checked_at: datetime
    action_id: str
    contract_id: str
    contract_version: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable audit representation."""
        return {
            "decision": self.decision.value,
            "reason_codes": list(self.reason_codes),
            "details": list(self.details),
            "checked_at": self.checked_at.isoformat(),
            "action_id": self.action_id,
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
        }

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
    """Machine-readable portion of the user's intent for a long-running task.

    Natural-language constraints and acceptance criteria are preserved as declarations.
    They are not automatically enforced unless an integration maps them to machine-checkable
    preconditions or validation rules.
    """

    contract_id: str
    version: int
    goal: str
    constraints: tuple[str, ...] = ()
    permitted_actions: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    required_approvals: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Evidence:
    """Evidence about a resource or condition.

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
    """A proposed action that must pass validation before execution."""

    action_id: str
    category: str
    consequential: bool = True
    required_evidence_ids: tuple[str, ...] = ()
    required_approval_ids: tuple[str, ...] = ()


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

"""Deterministic checks for intent drift before a proposed action."""

from __future__ import annotations

from datetime import datetime

from intent_integrity.models import (
    ActionRequest,
    Approval,
    ApprovalStatus,
    Decision,
    Evidence,
    IntentContract,
    ValidationContext,
    ValidationResult,
)


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _check_evidence(
    evidence_id: str,
    evidence: Evidence | None,
    now: datetime,
) -> tuple[list[str], list[str]]:
    """Return (blocking reasons, revalidation reasons) for one evidence item."""
    blocking: list[str] = []
    revalidation: list[str] = []

    if evidence is None:
        revalidation.append("REQUIRED_EVIDENCE_MISSING")
        return blocking, revalidation

    if evidence.evidence_id != evidence_id:
        revalidation.append("EVIDENCE_ID_MISMATCH")
    if not evidence.verified:
        revalidation.append("EVIDENCE_UNVERIFIED")
    if evidence.invalidated:
        revalidation.append("EVIDENCE_INVALIDATED")

    if not evidence.source.strip():
        revalidation.append("EVIDENCE_SOURCE_MISSING")

    if evidence.observed_at is None:
        revalidation.append("EVIDENCE_TIMESTAMP_MISSING")
    elif not _is_aware(evidence.observed_at):
        revalidation.append("EVIDENCE_TIMESTAMP_NOT_TIMEZONE_AWARE")
    elif not _is_aware(now):
        revalidation.append("VALIDATION_TIME_NOT_TIMEZONE_AWARE")
    else:
        age_seconds = (now - evidence.observed_at).total_seconds()
        if age_seconds < 0:
            revalidation.append("EVIDENCE_TIMESTAMP_IN_FUTURE")
        elif (
            evidence.freshness_ttl_seconds is not None
            and age_seconds > evidence.freshness_ttl_seconds
        ):
            revalidation.append("EVIDENCE_STALE")

    if evidence.freshness_ttl_seconds is not None and evidence.freshness_ttl_seconds < 0:
        revalidation.append("INVALID_FRESHNESS_POLICY")

    if evidence.resource_id is not None:
        if evidence.observed_version is None or evidence.current_version is None:
            revalidation.append("RESOURCE_VERSION_UNKNOWN")
        elif evidence.observed_version != evidence.current_version:
            revalidation.append("RESOURCE_VERSION_MISMATCH")

    return blocking, revalidation


def _check_approval(
    approval_id: str,
    approval: Approval | None,
    action: ActionRequest,
    now: datetime,
) -> tuple[list[str], list[str]]:
    """Return (blocking reasons, revalidation reasons) for one required approval."""
    blocking: list[str] = []
    revalidation: list[str] = []

    if approval is None:
        blocking.append("APPROVAL_MISSING")
        return blocking, revalidation

    if approval.approval_id != approval_id:
        blocking.append("APPROVAL_ID_MISMATCH")

    if approval.status == ApprovalStatus.REVOKED:
        blocking.append("APPROVAL_REVOKED")
    elif approval.status != ApprovalStatus.APPROVED:
        blocking.append("APPROVAL_NOT_APPROVED")

    if approval.expires_at is not None:
        if not _is_aware(approval.expires_at) or not _is_aware(now):
            blocking.append("APPROVAL_EXPIRY_TIME_INVALID")
        elif approval.expires_at <= now:
            blocking.append("APPROVAL_EXPIRED")

    if approval.allowed_actions and action.category not in approval.allowed_actions:
        blocking.append("APPROVAL_SCOPE_MISMATCH")

    return blocking, revalidation


def _requirements_for_action(
    requirements: tuple[tuple[str, tuple[str, ...]], ...],
    category: str,
) -> tuple[str, ...]:
    """Resolve requirements from trusted, contract-owned policy."""
    resolved: list[str] = []
    for action_category, identifiers in requirements:
        if action_category == category:
            resolved.extend(identifiers)
    return tuple(dict.fromkeys(resolved))


def validate_action(
    contract: IntentContract,
    action: ActionRequest,
    context: ValidationContext,
) -> ValidationResult:
    """Validate whether an action is currently eligible to execute.

    This function performs no side effects and does not call a model or external service.
    Integrations must create ActionRequest objects at a trusted action boundary and must not
    execute when the decision is anything other than ALLOW.
    """
    blocking: list[str] = []
    revalidation: list[str] = []
    details: list[str] = []

    if not contract.contract_id.strip() or not contract.goal.strip() or contract.version < 1:
        blocking.append("INVALID_CONTRACT")
        details.append("Contract ID, goal, and positive version are required.")

    if not action.action_id.strip() or not action.category.strip():
        blocking.append("INVALID_ACTION")
        details.append("Action ID and action category are required.")

    if action.category in contract.prohibited_actions:
        blocking.append("ACTION_PROHIBITED")
        details.append(f"Action category '{action.category}' is explicitly prohibited.")
    elif action.category not in contract.permitted_actions:
        blocking.append("ACTION_NOT_PERMITTED")
        details.append(f"Action category '{action.category}' is not on the allowlist.")

    if (
        context.active_contract_version is not None
        and context.active_contract_version != contract.version
    ):
        revalidation.append("CONTRACT_VERSION_CHANGED")
        details.append("The active contract version differs from the version being checked.")

    if not _is_aware(context.now):
        revalidation.append("VALIDATION_TIME_NOT_TIMEZONE_AWARE")
        details.append("Validation time must include timezone information.")

    required_evidence_ids = _requirements_for_action(
        contract.required_evidence_by_action, action.category
    )
    for evidence_id in required_evidence_ids:
        evidence = context.evidence.get(evidence_id)
        evidence_blocking, evidence_revalidation = _check_evidence(
            evidence_id, evidence, context.now
        )
        blocking.extend(evidence_blocking)
        revalidation.extend(evidence_revalidation)
        if evidence_blocking or evidence_revalidation:
            details.append(
                f"Evidence '{evidence_id}' is missing, stale, invalidated, or unverifiable."
            )

    required_approval_ids = list(
        _requirements_for_action(contract.required_approvals_by_action, action.category)
    )
    if action.category in contract.consequential_actions:
        required_approval_ids.extend(contract.required_approvals)

    for approval_id in dict.fromkeys(required_approval_ids):
        approval = context.approvals.get(approval_id)
        approval_blocking, approval_revalidation = _check_approval(
            approval_id, approval, action, context.now
        )
        blocking.extend(approval_blocking)
        revalidation.extend(approval_revalidation)
        if approval_blocking or approval_revalidation:
            details.append(f"Approval '{approval_id}' is not currently valid for this action.")

    if blocking:
        decision = Decision.BLOCK
    elif revalidation:
        decision = Decision.REVALIDATION_REQUIRED
    else:
        decision = Decision.ALLOW
        details.append("All deterministic checks represented by this contract passed.")

    return ValidationResult(
        decision=decision,
        reason_codes=tuple(dict.fromkeys(blocking + revalidation)),
        details=tuple(details),
        checked_at=context.now,
        action_id=action.action_id,
        contract_id=contract.contract_id,
        contract_version=contract.version,
    )

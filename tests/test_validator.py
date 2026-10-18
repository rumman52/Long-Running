from datetime import datetime, timedelta, timezone

import pytest

from intent_integrity import (
    ActionRequest,
    Approval,
    ApprovalStatus,
    Decision,
    Evidence,
    IntentContract,
    ValidationContext,
    validate_action,
)


NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def make_contract(**overrides: object) -> IntentContract:
    values: dict[str, object] = {
        "contract_id": "task-001",
        "version": 1,
        "goal": "Merge a reviewed change after required checks pass",
        "constraints": ("Do not merge if the source changes after testing",),
        "permitted_actions": ("merge_pull_request", "run_tests"),
        "prohibited_actions": ("delete_repository",),
        "assumptions": (),
        "required_approvals": (),
        "acceptance_criteria": ("Required checks pass",),
    }
    values.update(overrides)
    return IntentContract(**values)  # type: ignore[arg-type]


def make_action(**overrides: object) -> ActionRequest:
    values: dict[str, object] = {
        "action_id": "action-001",
        "category": "merge_pull_request",
        "consequential": True,
        "required_evidence_ids": ("tests",),
        "required_approval_ids": ("review",),
    }
    values.update(overrides)
    return ActionRequest(**values)  # type: ignore[arg-type]


def make_context(**overrides: object) -> ValidationContext:
    evidence = Evidence(
        evidence_id="tests",
        source="ci://run/123",
        observed_at=NOW - timedelta(seconds=30),
        resource_id="repo:example/pull/1",
        observed_version="commit-abc",
        current_version="commit-abc",
        freshness_ttl_seconds=300,
    )
    approval = Approval(
        approval_id="review",
        status=ApprovalStatus.APPROVED,
        expires_at=NOW + timedelta(minutes=10),
        allowed_actions=("merge_pull_request",),
    )
    values: dict[str, object] = {
        "now": NOW,
        "evidence": {"tests": evidence},
        "approvals": {"review": approval},
        "active_contract_version": 1,
    }
    values.update(overrides)
    return ValidationContext(**values)  # type: ignore[arg-type]


def test_all_valid_conditions_allow_action() -> None:
    result = validate_action(make_contract(), make_action(), make_context())
    assert result.decision == Decision.ALLOW
    assert result.reason_codes == ()


def test_prohibited_action_is_blocked() -> None:
    action = make_action(category="delete_repository")
    result = validate_action(make_contract(), action, make_context())
    assert result.decision == Decision.BLOCK
    assert "ACTION_PROHIBITED" in result.reason_codes


def test_action_not_on_allowlist_is_blocked() -> None:
    action = make_action(category="send_email")
    result = validate_action(make_contract(), action, make_context())
    assert result.decision == Decision.BLOCK
    assert "ACTION_NOT_PERMITTED" in result.reason_codes


def test_missing_required_evidence_requires_revalidation() -> None:
    result = validate_action(make_contract(), make_action(), make_context(evidence={}))
    assert result.decision == Decision.REVALIDATION_REQUIRED
    assert "REQUIRED_EVIDENCE_MISSING" in result.reason_codes


def test_stale_evidence_requires_revalidation() -> None:
    stale = Evidence(
        evidence_id="tests",
        source="ci://run/123",
        observed_at=NOW - timedelta(hours=1),
        resource_id="repo:example/pull/1",
        observed_version="commit-abc",
        current_version="commit-abc",
        freshness_ttl_seconds=60,
    )
    result = validate_action(
        make_contract(), make_action(), make_context(evidence={"tests": stale})
    )
    assert result.decision == Decision.REVALIDATION_REQUIRED
    assert "EVIDENCE_STALE" in result.reason_codes


def test_changed_resource_version_requires_revalidation() -> None:
    changed = Evidence(
        evidence_id="tests",
        source="ci://run/123",
        observed_at=NOW - timedelta(seconds=10),
        resource_id="repo:example/pull/1",
        observed_version="commit-old",
        current_version="commit-new",
        freshness_ttl_seconds=300,
    )
    result = validate_action(
        make_contract(), make_action(), make_context(evidence={"tests": changed})
    )
    assert result.decision == Decision.REVALIDATION_REQUIRED
    assert "RESOURCE_VERSION_MISMATCH" in result.reason_codes


def test_invalidated_evidence_requires_revalidation() -> None:
    evidence = make_context().evidence["tests"]
    invalidated = Evidence(
        evidence_id=evidence.evidence_id,
        source=evidence.source,
        observed_at=evidence.observed_at,
        resource_id=evidence.resource_id,
        observed_version=evidence.observed_version,
        current_version=evidence.current_version,
        freshness_ttl_seconds=evidence.freshness_ttl_seconds,
        invalidated=True,
    )
    result = validate_action(
        make_contract(), make_action(), make_context(evidence={"tests": invalidated})
    )
    assert result.decision == Decision.REVALIDATION_REQUIRED
    assert "EVIDENCE_INVALIDATED" in result.reason_codes


def test_unverified_evidence_requires_revalidation() -> None:
    evidence = make_context().evidence["tests"]
    unverified = Evidence(
        evidence_id=evidence.evidence_id,
        source=evidence.source,
        observed_at=evidence.observed_at,
        resource_id=evidence.resource_id,
        observed_version=evidence.observed_version,
        current_version=evidence.current_version,
        freshness_ttl_seconds=evidence.freshness_ttl_seconds,
        verified=False,
    )
    result = validate_action(
        make_contract(), make_action(), make_context(evidence={"tests": unverified})
    )
    assert result.decision == Decision.REVALIDATION_REQUIRED
    assert "EVIDENCE_UNVERIFIED" in result.reason_codes


@pytest.mark.parametrize(
    ("status", "expected_reason"),
    [
        (ApprovalStatus.REVOKED, "APPROVAL_REVOKED"),
        (ApprovalStatus.PENDING, "APPROVAL_NOT_APPROVED"),
    ],
)
def test_revoked_or_pending_approval_blocks_action(
    status: ApprovalStatus, expected_reason: str
) -> None:
    approval = Approval(
        approval_id="review",
        status=status,
        expires_at=NOW + timedelta(minutes=10),
        allowed_actions=("merge_pull_request",),
    )
    result = validate_action(
        make_contract(), make_action(), make_context(approvals={"review": approval})
    )
    assert result.decision == Decision.BLOCK
    assert expected_reason in result.reason_codes


def test_expired_approval_blocks_action() -> None:
    approval = Approval(
        approval_id="review",
        status=ApprovalStatus.APPROVED,
        expires_at=NOW,
        allowed_actions=("merge_pull_request",),
    )
    result = validate_action(
        make_contract(), make_action(), make_context(approvals={"review": approval})
    )
    assert result.decision == Decision.BLOCK
    assert "APPROVAL_EXPIRED" in result.reason_codes


def test_missing_approval_blocks_action() -> None:
    result = validate_action(make_contract(), make_action(), make_context(approvals={}))
    assert result.decision == Decision.BLOCK
    assert "APPROVAL_MISSING" in result.reason_codes


def test_approval_scope_mismatch_blocks_action() -> None:
    approval = Approval(
        approval_id="review",
        status=ApprovalStatus.APPROVED,
        expires_at=NOW + timedelta(minutes=10),
        allowed_actions=("run_tests",),
    )
    result = validate_action(
        make_contract(), make_action(), make_context(approvals={"review": approval})
    )
    assert result.decision == Decision.BLOCK
    assert "APPROVAL_SCOPE_MISMATCH" in result.reason_codes


def test_contract_version_change_requires_revalidation() -> None:
    result = validate_action(
        make_contract(version=2),
        make_action(),
        make_context(active_contract_version=1),
    )
    assert result.decision == Decision.REVALIDATION_REQUIRED
    assert "CONTRACT_VERSION_CHANGED" in result.reason_codes


def test_contract_required_approval_applies_to_consequential_action() -> None:
    contract = make_contract(required_approvals=("security-review",))
    context = make_context(
        approvals={
            "review": make_context().approvals["review"],
            "security-review": Approval(
                approval_id="security-review",
                status=ApprovalStatus.APPROVED,
                expires_at=NOW + timedelta(minutes=5),
                allowed_actions=("merge_pull_request",),
            ),
        }
    )
    result = validate_action(contract, make_action(), context)
    assert result.decision == Decision.ALLOW


def test_non_consequential_action_does_not_require_contract_level_approval() -> None:
    contract = make_contract(required_approvals=("security-review",))
    action = make_action(consequential=False, required_approval_ids=())
    result = validate_action(contract, action, make_context(approvals={}))
    assert result.decision == Decision.ALLOW


def test_audit_representation_is_json_friendly() -> None:
    result = validate_action(make_contract(), make_action(), make_context())
    payload = result.to_dict()
    assert payload["decision"] == "ALLOW"
    assert payload["contract_id"] == "task-001"
    assert payload["checked_at"] == NOW.isoformat()


def test_naive_evidence_timestamp_requires_revalidation() -> None:
    evidence = Evidence(
        evidence_id="tests",
        source="ci://run/123",
        observed_at=datetime(2026, 10, 18, 11, 59),
        resource_id="repo:example/pull/1",
        observed_version="commit-abc",
        current_version="commit-abc",
        freshness_ttl_seconds=300,
    )
    result = validate_action(
        make_contract(), make_action(), make_context(evidence={"tests": evidence})
    )
    assert result.decision == Decision.REVALIDATION_REQUIRED
    assert "EVIDENCE_TIMESTAMP_NOT_TIMEZONE_AWARE" in result.reason_codes


def test_future_evidence_timestamp_requires_revalidation() -> None:
    evidence = Evidence(
        evidence_id="tests",
        source="ci://run/123",
        observed_at=NOW + timedelta(seconds=5),
        resource_id="repo:example/pull/1",
        observed_version="commit-abc",
        current_version="commit-abc",
        freshness_ttl_seconds=300,
    )
    result = validate_action(
        make_contract(), make_action(), make_context(evidence={"tests": evidence})
    )
    assert result.decision == Decision.REVALIDATION_REQUIRED
    assert "EVIDENCE_TIMESTAMP_IN_FUTURE" in result.reason_codes

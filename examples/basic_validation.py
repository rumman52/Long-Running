"""Minimal, side-effect-free example of intent integrity validation."""

from datetime import datetime, timedelta, timezone

from intent_integrity import (
    ActionRequest,
    Approval,
    ApprovalStatus,
    Evidence,
    IntentContract,
    ValidationContext,
    validate_action,
)


now = datetime.now(timezone.utc)

contract = IntentContract(
    contract_id="merge-pr-42",
    version=1,
    goal="Merge the reviewed pull request only if tests still match the current commit.",
    permitted_actions=("merge_pull_request", "run_tests"),
    prohibited_actions=("delete_repository",),
    required_approvals=("review-approval",),
)

action = ActionRequest(
    action_id="merge-pr-42-step-3",
    category="merge_pull_request",
    consequential=True,
    required_evidence_ids=("ci-tests",),
)

evidence = Evidence(
    evidence_id="ci-tests",
    source="ci://example/runs/123",
    observed_at=now - timedelta(seconds=20),
    resource_id="repository:example/project/pull/42",
    observed_version="commit-abc",
    current_version="commit-abc",
    freshness_ttl_seconds=120,
)

approval = Approval(
    approval_id="review-approval",
    status=ApprovalStatus.APPROVED,
    expires_at=now + timedelta(minutes=5),
    allowed_actions=("merge_pull_request",),
)

context = ValidationContext(
    now=now,
    evidence={"ci-tests": evidence},
    approvals={"review-approval": approval},
    active_contract_version=1,
)

result = validate_action(contract, action, context)
print(result.to_dict())

# This example only validates. It does not execute a merge or call GitHub.

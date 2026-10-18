# Intent Contract — Initial Semantics

An intent contract captures the machine-readable parts of a user's request that a long-running agent must preserve. The host application must authorize and version the active contract; model output alone cannot change enforcement policy.

## Required concepts

- **contract_id:** stable task identifier.
- **version:** positive integer incremented when the contract changes.
- **goal:** concise statement of the requested outcome.
- **constraints:** declared limits; natural-language values are not enforced by the initial validator.
- **permitted_actions:** explicit allowlist of action categories.
- **prohibited_actions:** explicit denylist; denylist takes precedence.
- **consequential_actions:** action categories that require contract-level approvals.
- **required_evidence_by_action:** mapping from action category to evidence IDs that must be checked before that action.
- **required_approvals_by_action:** mapping from action category to approval IDs that must be checked before that action.
- **assumptions:** assumptions, associated evidence IDs, and invalidation conditions.
- **required_approvals:** approval IDs required for every consequential action.
- **acceptance_criteria:** declared criteria for later outcome verification.

## Action request

An action request contains only an action ID and category. Requirements are resolved from the active, trusted contract. This prevents the model from omitting a required evidence ID, changing the consequential flag, or removing an approval requirement when proposing an action.

## Evidence freshness

Evidence can be re-used only when it is verified, not explicitly invalidated, has a valid timezone-aware observation timestamp, is not from the future, satisfies its freshness TTL (when configured), and matches the current resource version when a versioned resource is involved.

If a required versioned resource's current version cannot be read, the validator requires revalidation.

## Approval validity

An approval must exist, be APPROVED, not be expired, and either have no action-category restriction or explicitly permit the proposed action category. A missing, pending, revoked, expired, or out-of-scope approval blocks the action.

## Decision values

- **ALLOW:** represented checks passed.
- **BLOCK:** an explicit policy or authorization check failed.
- **REVALIDATION_REQUIRED:** required evidence or state must be refreshed before execution.

These decisions are not interchangeable. In particular, revalidation is not implicit permission to retry or execute.

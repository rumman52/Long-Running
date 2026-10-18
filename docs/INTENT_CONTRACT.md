# Intent Contract — Initial Semantics

An intent contract captures the machine-readable parts of a user's request that a long-running agent must preserve.

## Required concepts

- **contract_id:** stable task identifier.
- **version:** positive integer incremented when the contract changes.
- **goal:** concise statement of the requested outcome.
- **constraints:** declared limits; natural-language values are not enforced by the initial validator.
- **permitted_actions:** explicit allowlist of action categories.
- **prohibited_actions:** explicit denylist; denylist takes precedence.
- **assumptions:** assumptions, associated evidence IDs, and invalidation conditions.
- **required_approvals:** approval IDs required for consequential actions.
- **acceptance_criteria:** declared criteria for later outcome verification.

## Action request

Each action has a unique action ID and a category. The caller declares whether it is consequential and lists evidence and approval IDs required for that specific action.

The integration must not let the model lower the consequential flag or remove requirements from an action without trusted policy logic.

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

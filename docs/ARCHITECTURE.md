# Architecture — Milestone 1

## Goal

Detect intent drift before an action is executed by checking structured user intent against current evidence and authorization state.

## Components

- **IntentContract:** durable, versioned representation of a task goal, constraints, action allowlist/denylist, assumptions, approval requirements, and acceptance criteria.
- **Evidence:** observation metadata including source, timestamp, resource identity/version, freshness policy, and explicit invalidation/verification flags.
- **ActionRequest:** proposed action category plus evidence and approvals required for that action.
- **ValidationContext:** current time and trusted evidence/approval observations supplied by the integration.
- **Validator:** pure, deterministic function returning ALLOW, BLOCK, or REVALIDATION_REQUIRED.
- **ValidationResult:** reason codes and an audit-friendly record of the decision.

## Decision semantics

1. **BLOCK:** a hard constraint fails, an action is not allowlisted, or a required approval is missing, pending, revoked, expired, or out of scope.
2. **REVALIDATION_REQUIRED:** required evidence is absent, stale, invalidated, unverified, timestamp-invalid, or inconsistent with the current resource version; or the active contract version differs.
3. **ALLOW:** all checks represented by this validator passed.

Blocking reasons take precedence over revalidation reasons. A blocked action must not execute. A revalidation-required action must not execute until the integration obtains fresh evidence or the required authorization and validates again.

## Trust boundary

The validator does not trust model-generated claims as evidence. Evidence and approval records must come from trusted integration code or authenticated systems. A model may help propose a contract, but contract changes must be validated and versioned by the host application.

## Limits of this milestone

- Natural-language constraints and acceptance criteria are stored, not semantically enforced.
- No action executor, external connector, database, model client, or persistent event store exists yet.
- A single pre-action check cannot eliminate time-of-check/time-of-use races. Integrations should use conditional writes, ETags, compare-and-swap, idempotency keys, or equivalent provider guarantees when available, then verify the result.
- This core cannot force an arbitrary agent to use it. Effective enforcement requires a trusted tool/action boundary that prevents bypasses.
- Audit records returned by the current function are not yet persisted or tamper-evident.

## Next milestones

1. Add a versioned JSON Schema and serialization/deserialization.
2. Define the portable Agent Skill package.
3. Add a controlled tool boundary and one adapter (initially MCP).
4. Add persistence, event sequencing, and race-condition tests.
5. Add a second independent agent-framework adapter and conformance suite.

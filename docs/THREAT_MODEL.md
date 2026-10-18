# Threat Model — Initial Draft

## Assets to protect

- User intent and explicit constraints.
- Authorization and approval state.
- Evidence used to justify consequential actions.
- Integrity of validation decisions and audit records.
- External systems affected by agent actions.

## Threats in scope

| Threat | Initial mitigation |
|---|---|
| Evidence is stale | Enforce freshness policy and compare observed/current resource versions |
| Evidence is manually invalidated | Reject invalidated evidence and require revalidation |
| Approval is revoked or expired | Block action based on current approval state |
| Action is outside the user's allowlist | Block non-allowlisted or explicitly prohibited categories |
| Model claims a check passed without evidence | Accept evidence only from trusted integration context |
| Contract version changes mid-task | Require revalidation when active and evaluated versions differ |
| Required evidence is missing | Return REVALIDATION_REQUIRED |
| Approval is missing or out of scope | Return BLOCK |

## Threats not yet solved

- A malicious or compromised adapter can lie about resource versions or approvals.
- An agent can bypass the validator if the integration does not mediate all consequential actions.
- A resource can change after validation and before the action executes (TOCTOU race).
- The current audit record is not persisted, signed, or tamper-evident.
- Natural-language constraints may be ambiguous or incorrectly translated into the contract.
- The model may omit relevant assumptions when proposing the initial contract.
- External providers may not expose reliable version checks, conditional writes, or idempotency support.

## Security requirements

1. Never treat missing information as proof that a condition is satisfied.
2. Enforce policy in trusted code, not only in prompts.
3. Require authenticated sources for approvals and evidence in real integrations.
4. Revalidate at the action boundary, as close to execution as practical.
5. Use provider-supported concurrency controls where available.
6. Record explicit reason codes for blocks and revalidation requirements.
7. Test attempted bypasses and ambiguous failures before production claims.

This document is a starting threat model, not a security certification.

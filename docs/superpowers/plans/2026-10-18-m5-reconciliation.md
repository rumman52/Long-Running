# External Outcome Reconciliation Implementation Plan

**Goal:** Recover ambiguous external operations without blindly repeating their effects.

**Architecture:** A trusted provider protocol executes and looks up immutable operations using
stable idempotency keys and optional resource-version conditions. SQLite atomically stores
the operation, action claim, and audit event. A coordinator reconciles CLAIMED/UNKNOWN records
and permits explicit retries only after an authoritative NOT_APPLIED outcome, current
authorization, and a valid provider idempotency deadline.

**Tech stack:** Python 3.11+, SQLite, existing deterministic engine, pytest.

**Spec:** M5 in `docs/ROADMAP.md`; provider guarantees and boundaries in
`docs/EXTERNAL_RECONCILIATION.md` (created with the implementation).

## Constraints and review focus

- No runtime dependencies; existing callback execution remains fail closed.
- The host registers trusted providers and constructs logical operation identities.
- Never reset an UNKNOWN claim or retry using a new key.
- Persist requests before calling providers; retry payloads and version conditions cannot change.
- Late results cannot overwrite newer state; compare revisions inside a SQLite transaction.
- A provider must enforce atomic idempotency, payload binding, and the supplied deadline.
- Lookup errors, malformed results, missing providers, expiry, and stale authorization pause writes.

## Tasks

- [x] Write failure tests for response loss, crash before/after effects, same-operation duplicates,
  stale versions, provider failures, expired keys, and concurrent reconciliation/retry.
- [x] Run the tests and confirm the missing coordinator is detected.
- [x] Add `reconciliation.py` with `ExternalOperation`, `ProviderOutcome`, `OutcomeStatus`,
  `ReconciliationProvider`, and `ExternalActionCoordinator.execute/reconcile/retry/reconcile_pending`.
- [x] Extend `events.py` and `store.py` with durable external records, atomic claims plus events,
  immutable operation storage, unique provider operation identity, and revision-checked transitions.
- [x] Run focused tests; fix only observed failures and review state transitions.
- [x] Export public interfaces, document provider obligations and an executable local example,
  and update M5's roadmap evidence.
- [x] Run the whole suite, Ruff, mypy, and the examples. Publish the reviewed result through a PR with CI as the integration gate.

# Implementation Roadmap

A milestone is complete only when its acceptance criteria are tested and the evidence is available. A file existing is not proof that a capability works.

## M1 — Intent Contract and Deterministic Validation Core

**Status: Implemented in the repository.** Verify the latest CI run before release.

- [x] Typed intent, action, evidence, approval, and result models.
- [x] JSON Schema and strict JSON parsing/serialization.
- [x] ALLOW / BLOCK / REVALIDATION_REQUIRED semantics.
- [x] Evidence freshness, invalidation, resource-version and approval checks.
- [x] Unit tests for core validation and serialization.

## M2 — Runtime State, Event History, and Checkpoints

**Status: Initial implementation added; CI and integration qualification required.**

- [x] Versioned typed event model.
- [x] SQLite event sequence with duplicate-event handling and hash-chain verification.
- [x] Checkpoints with state hashes.
- [x] Durable action claims with fail-closed duplicate prevention.
- [x] UNKNOWN outcome state after callback exceptions.
- [x] Tests for event idempotency, hash checks, checkpoints, and action claims.
- [ ] Prove concurrency behavior across multiple processes and SQLite connections.
- [ ] Add migrations, retention policy, operational backup/restore, and database access-control guidance.

## M3 — Plan Drift and Recovery

**Status: Initial deterministic implementation added; broader evaluation required.**

- [x] Detect unauthorized plan actions and invalidated assumptions.
- [x] Detect missing dependencies, cycles, and acceptance-criteria gaps.
- [x] Recover from a checkpoint and replay events after its sequence.
- [x] Rebuild compact context anchored to the original contract and verified progress.
- [x] Require a persisted, current plan before guarded actions; block malformed, stale, or drifted plans.
- [x] Record host-confirmed assumption revalidation and require a fresh plan afterward.
- [x] Tests for plan drift and recovery.
- [ ] Add state-machine/property-based tests for illegal transitions and event sequences.
- [ ] Add a completion verifier that maps each acceptance criterion to trusted evidence.

## M4 — Portable Agent Skill and Controlled Action Boundary

**Status: Planned.**

- [ ] Publish an Agent Skills-compatible package and manifest.
- [ ] Define a stable adapter protocol for action proposals, trusted context, validation decisions, and results.
- [ ] Implement an MCP-facing adapter that mediates consequential tool calls.
- [ ] Prove blocked actions do not reach the underlying tool.
- [ ] Add bypass, prompt-injection, malformed-input, and adapter-failure tests.

## M5 — External Outcome Reconciliation

**Status: Planned.**

- [ ] Define provider-neutral interfaces for idempotency keys, conditional operations, and outcome lookup.
- [ ] Reconcile CLAIMED/UNKNOWN actions after restart or timeout.
- [ ] Ensure a retry cannot duplicate an external side effect.
- [ ] Add fault-injection tests for response loss, process crash, stale versions, and provider errors.

## M6 — Optional Semantic Drift Detection and Gemma Adapter

**Status: Planned.**

- [ ] Define a provider interface independent of the core validator.
- [ ] Add optional Gemma-based structured plan comparison.
- [ ] Validate all model output and treat semantic signals as advisory.
- [ ] Test malformed outputs, refusals, uncertainty, prompt injection, and model unavailability.
- [ ] Measure precision, recall, false pauses, missed drift, latency, and token overhead.

## M7 — Cross-Framework Conformance and Evaluation

**Status: Planned.**

- [ ] Integrate Shuddho as one consumer.
- [ ] Integrate one independent agent framework.
- [ ] Publish adapter conformance tests and compatibility matrix.
- [ ] Compare unmonitored, deterministic-only, and hybrid approaches.
- [ ] Measure prevented unsafe actions, task success, false blocks, recovery quality, overhead, and bypass resistance.

## M8 — Open-Source Release Readiness

**Status: Planned.**

- [ ] Select and add an explicit open-source license with maintainer approval.
- [ ] Add contribution and security reporting guidance.
- [ ] Review dependencies, supply-chain posture, and supported Python versions.
- [ ] Publish reproducible demos, limitations, benchmark methodology, and release notes.
- [ ] Run threat-model review and external code review.

## Definition of done

A release must provide reproducible install/run instructions, passing CI, meaningful test coverage for its advertised behavior, documented limitations, and evidence for security claims. “Universal drift detection” and “production-ready” are not acceptable claims until measured and independently reviewed.

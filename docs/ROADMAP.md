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
- [x] Pin the authorized contract in event history and require explicit versioned amendments.
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
- [x] Rebuild compact context anchored to the active authorized contract and verified progress.
- [x] Replay later valid plan updates, step-completion records, and action decisions after recovery.
- [x] Require a persisted, current plan before guarded actions; block malformed, stale, or drifted plans.
- [x] Record host-confirmed assumption revalidation and require a fresh plan afterward.
- [x] Tests for plan drift and recovery.
- [ ] Add state-machine/property-based tests for illegal transitions and event sequences.
- [x] Add a completion verifier that maps each acceptance criterion to host-supplied evidence from current-plan step records, with freshness checks and unresolved-outcome blocking.

## M4 — Portable Agent Skill and Controlled Action Boundary

**Status: Initial adapter, portable skill, and minimal MCP stdio scaffold implemented; full conformance and real-host qualification remain.**

- [x] Add an Agent Skills-compatible `SKILL.md` with explicit trust-boundary guidance.
- [x] Define a host-owned tool registry and adapter protocol for proposals, trusted context, decisions, and results.
- [x] Add a minimal MCP stdio server for initialization, tool listing, and guarded tool calls.
- [x] Test that blocked actions do not reach the underlying callback.
- [x] Add malformed-input, unknown-tool, duplicate-claim, and adapter-failure tests.
- [ ] Validate full MCP conformance with the official SDK and supported clients.
- [ ] Add adversarial bypass and prompt-injection evaluation against a real agent host.
- [ ] Integrate and qualify at least one independent agent framework.

## M5 — External Outcome Reconciliation

**Status: Implemented for provider-aware operations; live-provider qualification remains an integration requirement.**

- [x] Define provider-neutral interfaces for idempotency keys, conditional operations, and outcome lookup.
- [x] Reconcile provider-aware CLAIMED/UNKNOWN actions after restart or timeout without resubmission.
- [x] Guard explicit retries with the original identity, payload, key, deadline, version condition, and current authorization; provider-side atomic idempotency is required.
- [x] Add fault-injection tests for response loss, process crash, stale versions, and provider errors.

Evidence: `tests/test_reconciliation.py` also covers concurrent retry claims, stale observations,
expired approvals/keys, malformed responses, missing providers, atomic audit-write failures,
and completion verification after reconciliation. Run `python examples/external_reconciliation.py`
and the checks in [the reconciliation guide](EXTERNAL_RECONCILIATION.md). Legacy callback claims
without provider metadata remain fail closed. These local tests do not qualify a live service.

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

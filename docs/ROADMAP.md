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

**Status: Core persistence implementation and operational guidance added; deployment-specific qualification remains.**

- [x] Versioned typed event model.
- [x] Pin the authorized contract in event history and require explicit versioned amendments.
- [x] SQLite event sequence with duplicate-event handling and hash-chain verification.
- [x] Checkpoints with state hashes.
- [x] Durable action claims with fail-closed duplicate prevention.
- [x] UNKNOWN outcome state after callback exceptions.
- [x] Tests for event idempotency, hash checks, checkpoints, and action claims.
- [x] Test event appends and duplicate action claims across multiple processes and SQLite connections (`tests/test_store_concurrency.py`).
- [x] Add versioned schema migrations and migration tests.
- [x] Add verified online backup/restore operations and tests.
- [x] Document retention policy, filesystem access controls, backup handling, and operational checks in [Persistence Operations](PERSISTENCE_OPERATIONS.md). The library deliberately does not prune hash-chained event rows automatically.

## M3 — Plan Drift and Recovery

**Status: Deterministic recovery and bounded property-based tests implemented; broader runtime evaluation remains.**

- [x] Detect unauthorized plan actions and invalidated assumptions.
- [x] Detect missing dependencies, cycles, and acceptance-criteria gaps.
- [x] Recover from a checkpoint and replay events after its sequence.
- [x] Rebuild compact context anchored to the active authorized contract and verified progress.
- [x] Replay later valid plan updates, step-completion records, and action decisions after recovery.
- [x] Require a persisted, current plan before guarded actions; block malformed, stale, or drifted plans.
- [x] Record host-confirmed assumption revalidation and require a fresh plan afterward.
- [x] Tests for plan drift and recovery.
- [x] Add bounded property-based tests for generated event sequences, hash-chain integrity, terminal action-state transitions, and duplicate claims (`tests/test_state_properties.py`).
- [x] Add a completion verifier that maps each acceptance criterion to host-supplied evidence from current-plan step records, with freshness checks and unresolved-outcome blocking.

## M4 — Portable Agent Skill and Controlled Action Boundary

**Status: Adapter, portable skill, MCP stdio scaffold, official-SDK smoke conformance, and LangGraph ToolNode adapter implemented; real-host adversarial qualification remains.**

- [x] Add an Agent Skills-compatible `SKILL.md` with explicit trust-boundary guidance.
- [x] Define a host-owned tool registry and adapter protocol for proposals, trusted context, decisions, and results.
- [x] Add a minimal MCP stdio server for initialization, tool listing, and guarded tool calls.
- [x] Test that blocked actions do not reach the underlying callback.
- [x] Add malformed-input, unknown-tool, duplicate-claim, and adapter-failure tests.
- [x] Exercise initialize, tool listing, allowed invocation, and blocked invocation through the official MCP Python SDK (`tests/test_mcp_sdk_conformance.py`). Full protocol conformance across supported clients remains unclaimed.
- [ ] Add adversarial bypass and prompt-injection evaluation against a real agent host.
- [x] Add an optional LangGraph ToolNode adapter and execute conformance tests through a compiled ToolNode. A live LLM and broader framework/version matrix are not qualified.

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

**Status: Implementation added; live Gemma measurements and broader independent evaluation remain pending.**

- [x] Define a provider interface independent of the core validator.
- [x] Add optional Gemma-based structured plan comparison through an Ollama-compatible endpoint.
- [x] Validate all model output and treat semantic signals as advisory; semantic output cannot change core validator decisions.
- [x] Test malformed outputs, refusals, uncertainty, prompt injection, invalid references, and model unavailability.
- [x] Add a labelled starter dataset and reproducible evaluation harness for precision, recall, false-pause rate, missed-drift rate, latency, and token overhead.
- [ ] Run and review live Gemma measurements on an expanded, independently labelled dataset before publishing accuracy claims.

## M7 — Cross-Framework Conformance and Evaluation

**Status: Adapter-level conformance and synthetic evaluation implemented; live-host qualification remains.**

- [x] Add a Shuddho consumer bridge for non-consequential asynchronous ToolSpec handlers. Consequential and approval-required tools remain on Shuddho's native approved-action and provider-reconciliation path.
- [x] Add an optional LangGraph ToolNode adapter and a framework-level conformance test.
- [x] Publish adapter conformance tests and a compatibility matrix in Cross-Framework Conformance and Evaluation.
- [x] Add a reproducible comparison of unmonitored, deterministic-only, and hybrid approaches. CI uses frozen fixture signals; the harness can also run with the M6 Gemma/Ollama provider.
- [x] Calculate unsafe actions prevented, task success, false blocks, ambiguous-outcome recovery quality, local invocation overhead, semantic latency/token usage when a provider reports them, and registered-adapter bypass resistance.
- [ ] Wire the Shuddho bridge into the deployed Shuddho runtime and verify every consequential tool path; adapter tests alone do not prove live integration.
- [ ] Run and review M7 with a live Gemma provider on an expanded, independently labelled scenario set. Live semantic metrics remain unmeasured.

## M8 — Open-Source Release Readiness

**Status: Release-readiness baseline implemented on the integration branch; license sign-off, independent review, and release publication remain.**

- [x] Add an Apache-2.0 license candidate and matching package metadata.
- [ ] Obtain explicit maintainer approval of the license choice before release.
- [x] Add contribution guidance and a private-first security reporting policy in `CONTRIBUTING.md` and `SECURITY.md`.
- [x] Review the dependency set, add `pip-audit` CI and Dependabot updates, and define Python 3.11–3.14 as supported with 3.15 best-effort. Workflow Actions are pinned to verified commit SHAs; a full dependency lockfile remains outstanding and is documented as a residual supply-chain risk in the threat model.
- [x] Document runnable demos, limitations, benchmark methodology, and unreleased changes in the README, evaluation guide, and `CHANGELOG.md`.
- [x] Document a maintainer threat-model review and unresolved risks in `docs/THREAT_MODEL.md`.
- [ ] Obtain an independent external code/security review.
- [ ] Publish a versioned release after CI passes, license sign-off, and independent review.

## Definition of done

A release must provide reproducible install/run instructions, passing CI, meaningful test coverage for its advertised behavior, documented limitations, and evidence for security claims. “Universal drift detection” and “production-ready” are not acceptable claims until measured and independently reviewed.

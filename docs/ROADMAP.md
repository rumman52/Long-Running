# Roadmap

This roadmap is evidence-driven. A milestone is complete only when its acceptance criteria pass; a file existing is not proof that a capability is complete.

## M1 — Intent Contract and Deterministic Validation Core

**Status: Implemented; CI verified.**

- [x] Typed intent contract, evidence, approval, action request, and result models.
- [x] JSON Schema 2020-12 for the portable contract.
- [x] Strict contract JSON parsing and serialization.
- [x] Deterministic ALLOW / BLOCK / REVALIDATION_REQUIRED decisions.
- [x] Action requirements resolved from contract policy rather than model-supplied per-action flags.
- [x] Tests for stale evidence, resource-version drift, invalidation, unknown evidence, approval failures, contract-version drift, and serialization.
- [x] CI across Python 3.11, 3.12, and 3.13 with pytest, Ruff, and mypy.

## M2 — Intent Drift State and Event Model

- [ ] Define a versioned event model for intent changes, assumption invalidation, evidence refresh, approval changes, and action attempts.
- [ ] Define deterministic rules that connect events to invalidation of affected evidence and plan steps.
- [ ] Add explicit state transitions and property-based tests for illegal transitions.
- [ ] Specify persistence-neutral interfaces without selecting a database prematurely.

## M3 — Portable Agent Skill Package

- [ ] Publish a skill manifest following the Agent Skills standard.
- [ ] Explain how compatible agents create and update intent contracts.
- [ ] Include examples and guidance for uncertainty, changed assumptions, and revalidation.
- [ ] Keep model instructions advisory; trusted runtime checks remain authoritative.

## M4 — Controlled Tool Boundary and First Adapter

- [ ] Implement an MCP-facing validation/tool boundary.
- [ ] Ensure required policy cannot be removed by model output.
- [ ] Validate as close to execution as practical.
- [ ] Add safe behavior for timeouts and ambiguous external outcomes.
- [ ] Add integration tests proving a blocked action does not execute.

## M5 — Gemma Intent Interpreter

- [ ] Add a provider interface so the core does not depend on a single model.
- [ ] Add an optional Gemma adapter for proposing structured intent contracts and summarizing detected drift.
- [ ] Validate model output against the JSON Schema and host policy.
- [ ] Test malformed outputs, refusals, uncertainty, and prompt-injection attempts.
- [ ] Keep all authorization and enforcement decisions in deterministic trusted code.

## M6 — Cross-Framework Conformance

- [ ] Integrate Shuddho as the first consumer.
- [ ] Integrate at least one independent agent environment.
- [ ] Publish a conformance suite and compatibility matrix.
- [ ] Measure prevented stale actions, false pauses, successful completion, latency overhead, and bypass resistance.

## M7 — Open-Source Release Readiness

- [ ] Select and add an open-source license with maintainer approval.
- [ ] Review dependencies and supply-chain posture.
- [ ] Add security reporting guidance and contribution instructions.
- [ ] Publish reproducible demos, limitations, benchmarks, and release notes.

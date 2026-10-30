# Long-Running Completion Ledger

**Audit date:** 2026-10-31  
**Project:** [rumman52/Long-Running](https://github.com/rumman52/Long-Running)  
**Scope:** Standalone, framework-neutral Python library. No external agent runtime is a project dependency.

This ledger separates implementation evidence from qualification and governance work. A passing test suite does not automatically close a deployment, security-review, provider, or release gate.

## Verified repository state

| Item | Verified state |
|---|---|
| Main revision | `330e5acf3f17e2b0c5b830570b42c85f9a39e07c` |
| M4 hardening | PR [#18](https://github.com/rumman52/Long-Running/pull/18) merged |
| M4 follow-up | PR [#19](https://github.com/rumman52/Long-Running/pull/19) open; exact head `1320443749ae3dde52b2a1fb32421adc9a48642c` |
| PR #19 Python CI | [#41119751437](https://github.com/rumman52/Long-Running/actions/runs/41119751437) passed |
| PR #19 dependency audit | [#41119751536](https://github.com/rumman52/Long-Running/actions/runs/41119751536) passed |
| M6 implementation | PR [#17](https://github.com/rumman52/Long-Running/pull/17) merged |
| Branch protection | Main reported `protected=false`; rulesets query returned none |
| Release | No published GitHub release found in the repository audit |
| Independent review | No review submission recorded on PR #18 or PR #19 |

## Milestone status

| Milestone | Implementation evidence | Outstanding work | Status |
|---|---|---|---|
| M1 — Deterministic intent core | Typed intent contract, action validation, authorization checks, unit tests | Independent runtime evaluation | Implemented; external evaluation pending |
| M2 — Persistence and checkpoints | SQLite event history, versioned schema, hash-chain verification, checkpoints, backup/restore, multi-process tests | Qualify intended OS/filesystem, operational backup target, restore drills, access control, and retention policy | Core implemented; deployment qualification pending |
| M3 — Drift and recovery | Deterministic plan checks, recovery/replay, completion verification, bounded property tests | Independent evaluation against representative long-running workloads | Core implemented; independent evaluation pending |
| M4 — Guarded action boundary | PR #18 merged bounded MCP/tool input and result handling plus LangGraph adversarial regression. PR #19 adds metadata rechecks, fail-closed metadata reads, and authorization-before-validation. Exact-head CI and audit passed. | Independent security review, live host tests, alternate-route bypass assessment, broader MCP client/version conformance | Implementation advanced; PR #19 review pending |
| M5 — External outcome reconciliation | Provider-neutral coordinator, durable CLAIMED/UNKNOWN states, lookup-before-retry, idempotency identity checks, crash/concurrency fault-injection tests | Real provider adapters and verification of provider-specific idempotency, conditional-write, and lookup guarantees | Core protocol implemented; provider qualification pending |
| M6 — Semantic drift | Provider-neutral provider interface, Gemma/Ollama adapter, strict bounded structured-output validation, 30-case balanced development corpus, 1–100 trial evaluator | Independent human labels, held-out dataset, live Gemma measurements, model/version-specific reporting | Development implementation merged; model qualification pending |
| M7 — Cross-framework conformance | Structural async ToolSpec adapter, LangGraph ToolNode adapter, MCP SDK smoke test, synthetic three-mode evaluation | Broader framework/version matrix and live LLM-driven host qualification | Adapter-level implementation; broader qualification pending |
| M8 — Release readiness | License candidate, contribution/security guidance, Dependabot, pip-audit, pinned workflow actions, demos, changelog, readiness/threat-model docs | Explicit license approval, reproducible dependency lock, transitive-license review, independent security review, branch protection, exact-release verification, versioned release | Baseline present; release gates open |

## Security follow-up evidence

PR #19 added two test-first regressions to the previous ToolSpec metadata tests:

1. An unpermitted tool must be blocked before its validator runs.
2. A ToolSpec metadata getter failure must return a structured fail-closed result without invoking the validator or handler.

Both tests failed against the prior implementation. The corrected code checks the current ToolSpec metadata inside an exception boundary, verifies the active contract's exact permission before validation, and then continues through the existing bounded snapshot and durable action-claim path.

The exact PR #19 head passed the full configured Python CI workflow and dependency audit. This is repository CI evidence, not an independent security review or live-host penetration test.

## External qualification and owner-controlled gates

These items cannot be truthfully completed by changing repository files alone:

1. **Independent security review:** a reviewer other than the PR author/implementer must inspect the merged M4 boundary and PR #19.
2. **Live host qualification:** the consuming application must prove every consequential action route is guarded and test alternate/direct-handler bypasses.
3. **MCP compatibility:** test the supported client/server version matrix; the current SDK smoke test is not full protocol conformance.
4. **M2 deployment qualification:** test the actual target operating system, filesystem, storage, backup destination, permissions, and restore process.
5. **M5 provider qualification:** select real providers and verify their idempotency keys, conditional writes, lookup consistency, retention windows, and ambiguity semantics.
6. **M6 independent labels and live Gemma:** two independent reviewers must label the cases and adjudicate disagreements; live provider runs must record exact model, configuration, latency, tokens, and per-case results.
7. **M8 license authority:** the maintainer must explicitly approve Apache-2.0 and confirm the repository has authority to license all included material.
8. **Repository governance:** enable branch protection, required reviews, and required status checks. The available GitHub integration can inspect the reported protection state but cannot change this repository setting.
9. **Public release:** create a versioned release only after the required reviews, lockfile, license sign-off, fresh exact-head checks, and release notes are complete.

## Claims not authorized by current evidence

Do not claim production certification, universal drift detection, universal interception of agent actions, provider-independent exactly-once execution, or measured live Gemma accuracy. The M7 fixture is synthetic. The M6 labels are provisional author-assigned labels. A framework adapter protects only calls routed through that adapter.

## Next executable repository tasks

- Expand LangGraph CI to test a declared minimum and current supported version.
- Add cross-platform persistence/reconciliation CI on Linux, Windows, and macOS.
- Generate and commit a reproducible dependency lockfile; make CI verify it.
- Add an independent-label review template and adjudication workflow for the M6 corpus.
- Re-run the full suite and dependency audit on each resulting exact PR head.

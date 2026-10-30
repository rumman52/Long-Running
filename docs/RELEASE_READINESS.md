# Open-Source Release Readiness

Audit date: 2026-10-31  
Repository: https://github.com/rumman52/Long-Running  
Audited main revision: `0f80f35aed2c820d9eeb780ec1c09c5d28221dc7`

## Executive status

Long-Running is a standalone, framework-neutral Python library. It is not part of, dependent on, or deployed as another agent runtime.

The M6 development-corpus and multi-trial evaluator work is merged. The MCP/guarded-tool input-hardening work has been rebased onto current main on branch `security/standalone-boundary-hardening-20261031`; its code-bearing head `a66e9a4f0c30f6d5de8fe91c15640eaadd83cb4c` passed Python CI [#41113067617](https://github.com/rumman52/Long-Running/actions/runs/41113067617) and dependency audit [#41113067648](https://github.com/rumman52/Long-Running/actions/runs/41113067648); independent review is pending. This audit does not treat candidate-branch code as merged-main functionality.

Main-branch evidence at the audited revision:

- Python CI [#41111205316](https://github.com/rumman52/Long-Running/actions/runs/41111205316): **passed**.
- Dependency Security Audit [#41111205252](https://github.com/rumman52/Long-Running/actions/runs/41111205252): **passed**.
- M6 PR #17 merged as commit [`0f80f35`](https://github.com/rumman52/Long-Running/commit/0f80f35aed2c820d9eeb780ec1c09c5d28221dc7). Exact-head Python CI [#41102632889](https://github.com/rumman52/Long-Running/actions/runs/41102632889) and dependency audit [#41102633109](https://github.com/rumman52/Long-Running/actions/runs/41102633109) passed.

This is an engineering readiness review, not a production security certification or independent penetration test.

## Readiness matrix

| Area | Evidence | Remaining gate |
|---|---|---|
| M1 deterministic core | Typed contracts, schema validation, action decisions, unit tests | Independent runtime evaluation |
| M2 persistence | SQLite event history, checkpoints, migrations, multi-process tests, verified backup/restore | Qualify target OS/filesystem, restore drills, backup target, access controls, and retention policy |
| M3 recovery | Deterministic drift checks, replay, completion verifier, bounded property tests | Broader independent runtime evaluation |
| M4 guarded boundary | Portable skill, guarded adapter, MCP JSON-RPC subset, official MCP SDK 2.x smoke test | Code-bearing candidate head passed exact-head CI and dependency audit; independent review, live LLM host tests, direct-handler bypass assessment, and broader MCP client matrix remain |
| M5 reconciliation | Provider-neutral coordinator and local fault-injection tests | Real provider adapters and provider-specific idempotency/lookup guarantees |
| M6 semantic drift | Provider-neutral interface, Gemma/Ollama adapter, strict advisory-only output validation, 30 provisional cases, 1–100 trial evaluator | Independent labels, held-out test set, and live Gemma measurements |
| M7 framework conformance | Generic async ToolSpec adapter, LangGraph ToolNode adapter, compatibility matrix, synthetic evaluation; CI artifact #41113418138 reports 4/6 unsafe prevented in hybrid fixture, 80% safe-task success, one false block, and 100% registered-adapter probe resistance | Broader framework/version matrix and live LLM-driven host qualification; fixture metrics are not live-model evidence |
| M8 release process | Apache-2.0 candidate, contribution/security guidance, Dependabot, pip-audit, pinned workflow actions, demos and changelog | License sign-off, dependency lock and transitive-license review, independent external review, branch protection, and public release |

## Security and supply-chain observations

- The core package declares no mandatory runtime dependencies.
- Development and optional framework dependencies are declared in `pyproject.toml`.
- A full reproducible dependency lockfile is not committed. Fresh installs can resolve different transitive versions over time.
- CI runs Python 3.11–3.14 as the supported matrix; Python 3.15 is best-effort, not a supported release target.
- GitHub Actions are pinned to immutable commit SHAs. The dependency audit is time-bounded evidence, not proof that the dependency tree is permanently vulnerability-free.
- The repository's main branch currently reports `protected=false`; the active rulesets endpoint returned no rulesets. Required status-check enforcement is therefore not established.
- No published GitHub release was found during this audit.
- The Apache-2.0 license file and package metadata are present as a candidate. Maintainer approval and provenance/copyright confirmation have not been recorded.

## Required release gates

1. Obtain explicit maintainer approval of Apache-2.0 and confirm authority to license all included material.
2. Add a reproducible lockfile and review transitive dependency licenses, or document an approved alternative.
3. Merge the rebased security hardening only after exact-head CI and independent security review.
4. Complete live LLM-driven host testing, direct-handler/alternate-route bypass assessment, and broader MCP client/version conformance.
5. Qualify persistence, backup/restore, filesystem, and retention behavior in the intended deployment environment.
6. Qualify real provider idempotency, conditional-write, and outcome-lookup semantics before using M5 with external side effects.
7. Obtain independent human labels, create a held-out semantic dataset, and run/review live Gemma measurements before publishing model-accuracy claims.
8. Verify branch protection, required reviews, exact-head status checks, and release permissions.
9. Run all documented demos and checks from a fresh environment on the exact release commit.
10. Publish a versioned release only after all required gates are satisfied.

## Claims that are not justified yet

Do not describe the library as production-certified, universally capable of detecting semantic drift, guaranteed to intercept every agent action, or proven to prevent unsafe actions across arbitrary frameworks. Adapter tests do not prove that a consumer has no alternate unguarded route. Local reconciliation tests do not establish real provider guarantees. Synthetic benchmark scores are not live model accuracy.

No public release is authorized by this checklist.

# Open-Source Release Readiness

Audit date: 2026-10-31  
Repository: https://github.com/rumman52/Long-Running  
Audited main revision: `330e5acf3f17e2b0c5b830570b42c85f9a39e07c`

## Executive status

Long-Running is a standalone, framework-neutral Python library. It is not part of, dependent on, or deployed as another agent runtime.

M6's 30-case provisional development corpus and multi-trial evaluator are merged. M4's bounded MCP and guarded-tool input hardening merged in PR #18. The merged head passed Python CI and dependency audit, but PR #18 has no recorded independent review. PR #19 adds fail-closed ToolSpec metadata reads and checks contract permission before validation; exact head `1320443749ae3dde52b2a1fb32421adc9a48642c` passed Python CI [#41119751437](https://github.com/rumman52/Long-Running/actions/runs/41119751437) and dependency audit [#41119751536](https://github.com/rumman52/Long-Running/actions/runs/41119751536). PR #19 remains open without independent review. The project is not production-qualified or ready for a public release.

Main-branch evidence:

- Python CI [#41114684757](https://github.com/rumman52/Long-Running/actions/runs/41114684757): **passed** on audited main.
- Dependency Security Audit [#41114685142](https://github.com/rumman52/Long-Running/actions/runs/41114685142): **passed** on audited main.
- M4 PR #18 merged as commit [`330e5acf`](https://github.com/rumman52/Long-Running/commit/330e5acf3f17e2b0c5b830570b42c85f9a39e07c). Merged head Python CI [#41114350260](https://github.com/rumman52/Long-Running/actions/runs/41114350260) and dependency audit [#41114350246](https://github.com/rumman52/Long-Running/actions/runs/41114350246) passed. No independent review was recorded.
- M6 PR #17 merged. Exact-head Python CI [#41102632889](https://github.com/rumman52/Long-Running/actions/runs/41102632889) and dependency audit [#41102633109](https://github.com/rumman52/Long-Running/actions/runs/41102633109) passed.
- M7 synthetic evaluation artifact [#41113418138](https://github.com/rumman52/Long-Running/actions/runs/41113418138): hybrid fixture prevented 4/6 labelled unsafe scenarios, safe-task success was 80%, one safe scenario was falsely paused, and registered-adapter bypass probes passed. The semantic source was a hand-authored fixture, not a live model.

## Readiness matrix

| Area | Evidence | Remaining gate |
|---|---|---|
| M1 deterministic core | Typed contracts, schema validation, action decisions, unit tests | Independent runtime evaluation |
| M2 persistence | SQLite event history, checkpoints, migrations, multi-process tests, verified backup/restore | Qualify target OS/filesystem, restore drills, backup target, access controls, and retention policy |
| M3 recovery | Deterministic drift checks, replay, completion verifier, bounded property tests | Broader independent runtime evaluation |
| M4 guarded boundary | Portable skill, guarded adapter, bounded MCP JSON-RPC subset, official MCP SDK 2.x smoke test; PR #18 merged and PR #19 exact-head CI/audit passed | Independent security review, live LLM host tests, direct-handler bypass assessment, and broader MCP client matrix |
| M5 reconciliation | Provider-neutral coordinator and local fault-injection tests | Real provider adapters and provider-specific idempotency/lookup guarantees |
| M6 semantic drift | Provider-neutral interface, Gemma/Ollama adapter, strict advisory-only output validation, 30 provisional cases, 1–100 trial evaluator | Independent labels, held-out test set, and live Gemma measurements |
| M7 framework conformance | Generic async ToolSpec adapter, LangGraph ToolNode adapter, compatibility matrix, synthetic evaluation | Broader framework/version matrix and live LLM-driven host qualification |
| M8 release process | Apache-2.0 candidate, contribution/security guidance, Dependabot, pip-audit, pinned workflow actions, demos and changelog | License sign-off, dependency lock and transitive-license review, independent external review, branch protection, and public release |

## Security and supply-chain observations

- The core package declares no mandatory runtime dependencies.
- Development and optional framework dependencies are declared in `pyproject.toml`.
- A full reproducible dependency lockfile is not committed. Fresh installs can resolve different transitive versions over time.
- CI supports Python 3.11–3.14; Python 3.15 is best-effort, not a supported release target.
- GitHub Actions are pinned to immutable commit SHAs. The dependency audit is time-bounded evidence, not proof that the dependency tree is permanently vulnerability-free.
- The main branch reports `protected=false`; required status-check enforcement is not established.
- No published GitHub release was found during this audit.
- Apache-2.0 license text and package metadata are present, but maintainer approval and provenance/copyright confirmation have not been recorded.
- PR #18 merged without a recorded review submission. PR #19 has no independent review recorded at the time of this audit.

## Required release gates

1. Obtain explicit maintainer approval of Apache-2.0 and confirm authority to license all included material.
2. Add a reproducible lockfile and review transitive dependency licenses, or document an approved alternative.
3. Obtain independent security review of the merged M4 boundary and PR #19; fix findings before release.
4. Complete live LLM-driven host testing, direct-handler/alternate-route bypass assessment, and broader MCP client/version conformance.
5. Qualify persistence, backup/restore, filesystem, and retention behavior in the intended deployment environment.
6. Qualify real provider idempotency, conditional-write, and outcome-lookup semantics before using M5 with external side effects.
7. Obtain independent human labels, create a held-out semantic dataset, and run/review live Gemma measurements before publishing model-accuracy claims.
8. Enable branch protection, required reviews, and exact-head status checks.
9. Run all documented demos and checks from a fresh environment on the exact release commit.
10. Publish a versioned release only after all required gates are satisfied.

## Claims that are not justified yet

Do not describe the library as production-certified, universally capable of detecting semantic drift, guaranteed to intercept every agent action, or proven to prevent unsafe actions across arbitrary frameworks. Adapter tests do not prove that a consumer has no alternate unguarded route. Local reconciliation tests do not establish real provider guarantees. Synthetic benchmark scores are not live model accuracy.

No public release is authorized by this checklist.

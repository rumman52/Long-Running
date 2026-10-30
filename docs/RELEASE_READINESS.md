# Open-Source Release Readiness

Audit date: 2026-10-30  
Repository: https://github.com/rumman52/Long-Running  
Audited main revision: `9936b9c64345fcef943bc1603c7ffc0a017dba2d`  
MCP SDK repair: [PR #14](https://github.com/rumman52/Long-Running/pull/14)  
Standalone-scope documentation correction: [PR #15](https://github.com/rumman52/Long-Running/pull/15)  
Input-boundary hardening candidate: [PR #16](https://github.com/rumman52/Long-Running/pull/16)  
Semantic dataset/trial candidate: [PR #17](https://github.com/rumman52/Long-Running/pull/17)

## Summary

Long-Running is a standalone, framework-neutral Python library. Optional adapters are integration surfaces for independent consumers; the project does not depend on, deploy, or form part of any external agent runtime.

This is an early engineering implementation, not a production security certification.

The MCP Python SDK v2 conformance regression was repaired in PR #14 and merged to main. The previous failure was caused by stale camelCase test attributes; the MCP server's JSON-RPC response and guarded action behavior were not the cause.

Exact merged-main evidence:
- [Python CI #41096718636](https://github.com/rumman52/Long-Running/actions/runs/41096718636): **passed**.
- [Dependency Security Audit #41096718927](https://github.com/rumman52/Long-Running/actions/runs/41096718927): **passed**.
- PR #14 candidate-head CI passed Python 3.11–3.14, Python 3.15 best-effort, runtime and reconciliation examples, Ruff, strict mypy, LangGraph ToolNode conformance, and M7 synthetic evaluation.

PR #15 updates documentation to make the standalone project boundary explicit. Its exact-head Python CI #41097543123 and dependency audit #41097543149 passed. PR #15 remains open and has not been merged.

PR #16 now contains bounded MCP stdio input and JSON nesting, strict duplicate-key/non-finite parsing, guarded-tool argument/result limits, callback-input snapshotting, unknown-outcome handling for oversized results, and a compiled LangGraph adversarial regression. Exact candidate head `267ed56d9ad3d1d0f1ebe922a9f9670163e19522` passed Python CI [#41104798481](https://github.com/rumman52/Long-Running/actions/runs/41104798481) and dependency audit [#41104798516](https://github.com/rumman52/Long-Running/actions/runs/41104798516). PR #16 remains draft and unmerged, with no submitted independent review; the scripted LangGraph test is not live-LLM or universal-host qualification.

PR #17 expands the semantic development corpus from 8 to 30 balanced author-labelled cases and adds sequential multi-trial reporting (1–100 trials). Exact head `a26c7217b37c72ae2db01c3a5cc2bb168f360720` passed Python CI [#41102632889](https://github.com/rumman52/Long-Running/actions/runs/41102632889) and dependency audit [#41102633109](https://github.com/rumman52/Long-Running/actions/runs/41102633109). It remains open and unmerged; labels are provisional, not independent ground truth, and no live Gemma measurements are available.

An Apache-2.0 license candidate and matching package metadata are present. The maintainer must explicitly approve the license choice and confirm authority to license all repository material before a public release.

## Readiness checklist

| Area | Evidence in main | Remaining release gate |
|---|---|---|
| Core intent and deterministic validation | Typed contract, validator, schema, unit/property tests, and passing CI | Broader independent runtime evaluation |
| Persistence and recovery | SQLite event history, checkpoints, migrations, multi-process tests, backup/restore verification | Qualify target OS/filesystem/process model, backup target, restore drills, and retention policy |
| Guarded action boundary | Python adapter, portable skill, MCP stdio subset, official MCP SDK 2.x smoke test | Live LLM-driven host adversarial evaluation; verify all consumer routes and direct-handler exposure |
| MCP input robustness | PR #16 candidate adds 1,000,000-character records, JSON depth 128, strict duplicate/non-finite parsing, 1,000,000-byte tool argument/result bounds, depth 64, 100,000 nodes, callback snapshots, and unknown-outcome handling; exact-head CI/security passed | Draft/unmerged and awaiting independent review; broader MCP client/version matrix and live LLM host qualification remain |
| External outcome reconciliation | Provider-neutral coordinator and local fault-injection tests | Live provider adapters and provider-specific idempotency/lookup guarantees |
| Semantic drift | Provider-neutral interface, Gemma/Ollama adapter, strict output validation, advisory-only findings; PR #17 expands the provisional corpus to 30 balanced cases and adds multi-trial reporting with exact-head CI/security passed | Independent human labels, held-out set, and live Gemma measurements remain required |
| Cross-framework support | Optional structural async ToolSpec adapter, LangGraph ToolNode adapter, compatibility matrix, synthetic harness | Broader framework/version matrix and live LLM-driven host qualification; no external host deployment is required for the standalone package |
| License | Apache-2.0 candidate LICENSE and SPDX package metadata | Explicit maintainer approval and provenance/copyright review |
| Contribution process | CONTRIBUTING.md and pull-request template | Maintainer confirms governance fits the project |
| Vulnerability reporting | SECURITY.md with private-first reporting guidance | Confirm a monitored contact route; no published response SLA or bug-bounty program exists |
| Dependencies | Empty mandatory runtime dependency set, pip-audit workflow, Dependabot, workflow actions pinned to immutable SHAs | Full reproducible dependency lockfile and review of transitive dependency licenses |
| Python support | CI matrix for Python 3.11–3.14; Python 3.15 best-effort | Re-run full matrix on the exact release commit; do not claim 3.15 as supported yet |
| Threat model | Maintainer engineering review documents assets, boundaries, mitigations, and residual risk | Independent external security/code review remains outstanding |
| Release notes and demos | README, CHANGELOG.md, reproducible demos, benchmark methodology, and release checklist | Update against final release commit and preserve exact reproduction metadata |
| Repository governance | Main branch metadata reports `protected=false`; active repository rulesets API returns `[]`; required status-check enforcement is off | Owner must enable native branch protection/rulesets, require reviewed PRs and exact-head CI, and verify no bypass paths before release |
| Versioned release | No published GitHub release was returned by the releases API | Verify tags and publish only after license approval, independent review, and exact-commit qualification |

## Dependency and supply-chain observations

- The package declares no mandatory runtime dependencies. Development and optional framework dependencies are specified in `pyproject.toml`.
- The repository does not yet commit a full dependency lockfile. Fresh installs can therefore resolve different transitive versions over time.
- The `pip-audit` workflow audits the installed Python environment on pushes, pull requests, and a weekly schedule. A clean audit is time-bounded evidence, not proof that dependencies are vulnerability-free.
- Dependabot proposes updates for Python dependencies and GitHub Actions. Review update diffs, changelogs, permissions, and CI before accepting them.
- Workflow actions are pinned to immutable commit SHAs on main. This reduces mutable-tag risk but does not replace dependency locking or review.
- Review the license, maintenance status, and transitive dependency impact of every new package. Keep runtime dependencies minimal.

## Release procedure

1. Approve Apache-2.0 explicitly and verify the project's authority to license all included material.
2. Add and verify a reproducible lockfile for the supported Python matrix, or document a deliberate alternative release policy.
3. Ensure Python CI, framework conformance, M7 fixture evaluation, and dependency auditing pass on the exact release commit.
4. Obtain independent code/security review and resolve findings.
5. Run documented demos and test commands from a fresh environment.
6. Qualify persistence behavior on the intended deployment environment and review the retention policy.
7. Run and independently review live Gemma benchmarks before publishing model-performance claims.
8. Review the threat model, known limitations, supported Python matrix, README, and CHANGELOG.md.
9. Verify repository branch protection, release permissions, and tag policy.
10. Create a version tag and GitHub release only after all gates are satisfied.

## Do not claim yet

Do not describe the project as production-certified, universally capable of detecting semantic drift, guaranteed to intercept all agent actions, or proven to prevent unsafe actions across arbitrary frameworks. The host must mediate every consequential route; external outcomes require provider-specific reconciliation; deterministic checks do not understand every natural-language deviation.

## Unresolved engineering gates

- **M2:** deployment-specific filesystem, backup/restore, and retention qualification remain outside local unit-test evidence.
- **M3:** deterministic recovery and bounded property-based tests exist; broader independent runtime evaluation remains.
- **M4:** PR #16 input-boundary candidate passed exact-head Python CI and dependency audit but remains draft/unmerged and has no independent review. Its scripted LangGraph regression does not qualify a live LLM host or prove every consumer route is guarded. A broader MCP client/version matrix and direct-handler bypass assessment remain.
- **M5:** live provider adapters and provider-specific guarantees still require qualification. Local fault-injection tests do not prove a real provider's idempotency or outcome lookup semantics.
- **M6:** PR #17 expands the development corpus to 30 balanced author-assigned cases and adds multi-trial reporting, but labels are provisional and not independently reviewed. Live Gemma/Ollama measurements, independent labels, and a held-out test set remain required.
- **M7:** optional adapter-level tests and synthetic evaluation are implemented. Broader framework/version coverage and a reviewed live model-backed run remain. No external agent runtime deployment is a dependency or acceptance gate for this standalone project.
- **M8:** maintainer license approval, a reproducible dependency lockfile and transitive-license review, independent external code/security review, native branch protection, and a public versioned release remain outstanding.

No production security certification or public release is authorized by this checklist.
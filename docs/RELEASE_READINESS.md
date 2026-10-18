# Open-Source Release Readiness

Audit date: 2026-10-18  
Repository: https://github.com/rumman52/Long-Running  
Candidate branch: `feat/roadmap-completion-m2-m8`

## Summary

This is an early engineering implementation, not a production security certification. The candidate branch adds versioned SQLite migration and backup/restore helpers, process-concurrency tests, property-based tests, official MCP SDK smoke tests, cross-framework evaluation, and M8 release materials. Exact CI and dependency-audit results must be checked for the final candidate commit; neither substitutes for independent review.

An Apache-2.0 license candidate and matching package metadata are included. The maintainer must explicitly approve the license before merge/release and confirm authority to license all repository material and compatibility of third-party content.

## Readiness checklist

| Area | Evidence in candidate branch | Remaining release gate |
|---|---|---|
| License | Apache-2.0 candidate LICENSE and SPDX package metadata | Explicit maintainer approval; verify copyright and contribution authority |
| Contribution process | CONTRIBUTING.md and pull-request template | Maintainer confirms process fits project governance |
| Vulnerability reporting | SECURITY.md with private-first reporting guidance | Confirm maintainer contact route; enable GitHub private vulnerability reporting in repository settings if desired |
| Dependencies | Minimal runtime dependency set, pip-audit workflow, Dependabot, workflow actions pinned to verified commit SHAs | Establish a full dependency lockfile before a high-assurance release; review each audit result |
| Python support | CI matrix for Python 3.11–3.14 and best-effort 3.15 | Confirm the full matrix passes on the exact release commit; do not claim 3.15 support until maintained and consistently green |
| Demos | Side-effect-free demos and CI smoke execution | Confirm demo jobs pass on the final candidate commit |
| Persistence operations | Versioned migrations, backup/restore integrity tests, and operational guidance | Qualify the intended OS, filesystem, process supervisor, backup target, and retention policy |
| Limitations | README, runtime guide, threat model, roadmap, and release checklist distinguish code from qualification | Keep limitations synchronized with future changes |
| Benchmarks | M7 harness plus documented metrics and reporting protocol | Run and review live Gemma evaluation on expanded independent labels before quantitative model claims |
| Threat model | Assets, trust boundaries, threats, mitigations, residual risks, and deployment guidance | Re-review after adapter/semantic changes and before production claims |
| External review | Pull-request guidance requires independent review for security-sensitive changes | Independent external code/security review has not been completed; record review and resolve findings |
| Release notes | CHANGELOG.md and this checklist | Update with verified final changes and unresolved limitations |
| Versioned release | No public release has been published | Tag and publish only after the gates below pass |

## Dependency and supply-chain observations

- The package declares no mandatory runtime dependencies. Development and optional framework dependencies are specified in `pyproject.toml`.
- Workflow actions are pinned to verified immutable commit SHAs on the candidate branch. The repository does not yet commit a full dependency lockfile, so fresh installs can resolve different transitive versions over time.
- The `pip-audit` workflow audits the installed Python environment on pushes, pull requests, and a weekly schedule. A clean audit is time-bounded evidence, not proof that dependencies are vulnerability-free.
- Dependabot proposes updates for Python dependencies and GitHub Actions. Review update diffs, changelogs, permissions, and CI before accepting updates.
- Review the license, maintenance status, and transitive dependency impact of every new package. Keep runtime dependencies minimal.

## Release procedure

1. Approve Apache-2.0 explicitly and verify the project's authority to license all included material.
2. Ensure Python CI, framework conformance, M7 fixture evaluation, and dependency auditing pass on the exact release commit.
3. Obtain independent code/security review and resolve findings.
4. Run the documented demos and test commands from a fresh environment.
5. Qualify persistence behavior on the intended deployment environment and review the retention policy.
6. Run and independently review live Gemma benchmarks before publishing model-performance claims.
7. Review the threat model, known limitations, supported Python matrix, and README.
8. Update CHANGELOG.md with verified changes and unresolved limitations.
9. Create a version tag and GitHub release only after the above gates are satisfied.

## Do not claim yet

Do not describe the project as production-certified, universally capable of detecting semantic drift, guaranteed to intercept all agent actions, or proven to prevent unsafe actions across arbitrary frameworks. The host must mediate every consequential route; external outcomes require provider-specific reconciliation; deterministic checks do not understand every natural-language deviation.

## Unresolved integration gates

The Shuddho bridge is currently tested at the adapter boundary and is not wired into the deployed Shuddho runtime. The LangGraph adapter is tested through ToolNode but not through every version/provider combination or a live LLM. M6 accuracy and M7 hybrid model metrics remain unmeasured until a declared Gemma/Ollama run is recorded and independently reviewed. No independent external code/security review or public versioned release has been completed.

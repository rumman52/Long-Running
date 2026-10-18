# Open-Source Release Readiness

Audit date: 2026-10-18  
Repository: https://github.com/rumman52/Long-Running

## Summary

This is an early engineering implementation. The default branch includes the deterministic core, external-outcome reconciliation, and optional semantic comparator; the proposed completion branch adds SQLite migration/backup helpers, property-based tests, official MCP SDK smoke tests, cross-framework evaluation, and M8 release materials. At the audit point, the default branch had no GitHub license detected and no published releases. The exact release-candidate CI and audit results must be checked; neither substitutes for independent review.

This M8 change proposes Apache-2.0. The license must be explicitly approved by the maintainer before the change is merged. Before approving, confirm that the maintainer has the authority to license all material in the repository and that any third-party material has compatible terms.

## Readiness checklist

| Area | Evidence added | Remaining release gate |
|---|---|---|
| License | Candidate LICENSE and SPDX package metadata for Apache-2.0 | Explicit maintainer approval; verify copyright and contribution authority; merge the approved change |
| Contribution process | CONTRIBUTING.md and pull-request template | Maintainer should confirm the process fits the project's governance |
| Vulnerability reporting | SECURITY.md with private-reporting guidance | Enable GitHub private vulnerability reporting in repository settings if desired; confirm maintainer contact route |
| Dependencies | Minimal runtime dependency set; dependency audit workflow; Dependabot for pip and GitHub Actions | Review every audit result; pin actions to immutable SHAs and establish a lockfile before a high-assurance release |
| Python support | Proposed CI for 3.11–3.14 and best-effort 3.15 check | Confirm the complete branch CI matrix passes; do not claim 3.15 support until its job is green and maintained |
| Demos | Side-effect-free demo instructions and CI smoke execution | Confirm demo jobs pass on the proposed branch |
| Limitations | README, runtime guide, threat model, and roadmap distinguish implemented behavior from gaps | Keep limitations synchronized with future changes |
| Benchmarks | Metrics, scenarios, and reporting protocol documented | Add executable benchmark harness and raw results before making quantitative claims |
| Threat model | Assets, trust boundaries, threats, mitigations, and residual risks reviewed in docs/THREAT_MODEL.md | Re-review after adapter/semantic changes and before any production claim |
| External review | PR template calls for independent review on security-sensitive changes | Independent reviewer has not yet reviewed this repository; request and record review before release |
| Release notes | CHANGELOG.md and release checklist | Prepare versioned notes only after release scope and test evidence are approved |

## Dependency and supply-chain observations

- The package declares no mandatory runtime dependencies. The optional development extra contains pytest, Ruff, mypy, and jsonschema with minimum-version ranges.
- No dependency lockfile is currently committed. Fresh installs can resolve different transitive versions over time; the demo guide discloses this limitation.
- CI uses major-version tags for the official checkout and Python setup actions. Dependabot will track updates, but immutable SHA pinning is recommended before a high-assurance release.
- pip-audit checks the installed Python environment on pushes, pull requests, and a weekly schedule. A clean audit is time-bounded evidence, not proof that dependencies are vulnerability-free.
- Review the licenses and maintenance status of any new dependency before adding it. Keep runtime dependencies minimal.

## Release procedure

1. Approve the proposed license and verify the project's authority to license all included contributions.
2. Ensure CI and dependency auditing pass on the exact release commit.
3. Obtain independent code/security review and resolve findings.
4. Run the documented demos and test commands from a fresh environment.
5. Review the threat model, known limitations, supported Python matrix, and benchmark evidence.
6. Update CHANGELOG.md with verified changes and unresolved limitations.
7. Create a version tag and GitHub release only after the above gates are satisfied.

## Do not claim yet

Do not describe the project as production-certified, universally capable of detecting semantic drift, guaranteed to intercept all agent actions, or proven to prevent unsafe actions across arbitrary frameworks. The host must mediate every consequential route; external outcomes require provider-specific reconciliation; current deterministic checks do not understand every natural-language deviation.


## Current implementation gates

The proposed completion branch adds versioned SQLite schema migration, independent-process event/claim tests, backup/restore integrity checks, Hypothesis-generated regression tests, and a smoke test using the official MCP Python SDK. The M7 branch adds local LangGraph and Shuddho adapter tests plus a synthetic comparison harness; it does not prove that the deployed Shuddho runtime routes every action through the guard. M6 model accuracy remains unmeasured until a declared Gemma/Ollama run is recorded.

Do not merge or publish the proposed license until the maintainer explicitly approves Apache-2.0 and confirms authority to license all included material. Independent external code/security review remains a release blocker.

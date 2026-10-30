# Changelog

All notable changes to Intent Integrity are recorded here. This project has not published a GitHub release as of the M8 readiness review.

## Unreleased — M2–M8 integration and release-readiness baseline

### Added
- Versioned SQLite schema migrations, process-concurrency tests, and verified online backup/restore operations.
- Persistence operations guidance for retention decisions, filesystem permissions, backups, restores, and integrity incidents.
- Bounded property-based tests for event chains, terminal action states, and duplicate action claims.
- Official MCP Python SDK smoke-conformance tests and an optional LangGraph ToolNode adapter.
- Reproducible M7 evaluation harness and synthetic CI artifacts.
- Apache-2.0 license candidate, contribution/security guidance, dependency audit workflow, and Dependabot updates.
- Verified commit-SHA pins for GitHub Actions.
- Merged PR #18: bounded MCP JSON input and guarded-tool arguments/results, validated callback snapshots, unknown-outcome handling for oversized results, and compiled LangGraph adversarial regression. No independent review was recorded at merge. PR #19 adds fail-closed ToolSpec metadata reads and checks contract permission before validator invocation; exact head `1320443749ae3dde52b2a1fb32421adc9a48642c` passed Python CI #41119751437 and dependency audit #41119751536. Independent review remains pending.
- Merged PR #17: 30-case provisional semantic development corpus and sequential multi-trial evaluation reporting; independent labels, a held-out set, and live Gemma evaluation remain pending.

- Apache-2.0 license and SPDX package metadata, subject to maintainer approval of the M8 change.
- Contribution guidance and a responsible security-reporting process.
- Dependency auditing workflow and scheduled Dependabot updates for Python dependencies and GitHub Actions.
- Reproducible demo instructions, benchmark methodology, and a release-readiness checklist.
- Expanded threat model, trust boundaries, residual risks, and pre-release review gates.

### Changed
- CI targets Python 3.11–3.14 as supported versions and checks Python 3.15 on a best-effort basis.
- Documentation distinguishes implemented deterministic checks from unimplemented or unqualified production capabilities.

### Not yet claimed
- No independent external code review has been completed.
- No benchmark results proving detection effectiveness, lower false-positive rates, or production safety have been published.
- A passing test suite does not establish complete agent-framework interception or production security.

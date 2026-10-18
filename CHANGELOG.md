# Changelog

All notable changes to Intent Integrity are recorded here. This project has not published a GitHub release as of the M8 readiness review.

## Unreleased — M8 open-source readiness proposal

### Added
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

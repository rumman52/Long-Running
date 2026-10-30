# Long-Running Milestone Completion Plan

> **For agentic workers:** Use the executing-plans workflow to implement each task in order. Track completion in `docs/COMPLETION_LEDGER.md`.

**Goal:** Close repository-addressable engineering gaps in Long-Running while keeping independent review, provider qualification, maintainer approval, and release authorization explicit.

**Architecture:** Preserve the deterministic core and keep framework/provider integrations optional. Use CI matrices and immutable lockfiles for reproducibility; use explicit external qualification gates for behaviors that cannot be proven by local fixtures.

**Tech Stack:** Python 3.11–3.14, pytest, Ruff, mypy, SQLite, GitHub Actions, uv, LangGraph, MCP Python SDK, Gemma/Ollama optional provider.

**Spec:** `docs/ROADMAP.md`, `docs/THREAT_MODEL.md`, and `docs/RELEASE_READINESS.md`.

## Global Constraints

- Long-Running remains a standalone, framework-neutral Python library.
- Core runtime dependencies remain empty; integrations remain optional.
- Semantic-model output is advisory and never changes deterministic authorization.
- Unknown external outcomes must be reconciled before retry.
- Supported Python versions remain 3.11–3.14; Python 3.15 remains best-effort.
- Do not claim live-model accuracy from fixture scores or author-assigned labels.
- Do not publish a release without maintainer license approval and independent security review.

## Review Focus

- ToolSpec metadata getters that raise, mutate, or return invalid values must fail closed.
- Unpermitted tools must not execute validators or handlers.
- SQLite behavior must be exercised across supported operating systems without weakening transactional guarantees.
- Dependency lock resolution must cover supported Python versions and optional development/framework extras.
- Evaluation labels must remain explicitly provisional until independent review and adjudication.

---

### Task 1: ToolSpec boundary follow-up

**Files:** `src/intent_integrity/integrations/async_tool_spec.py`, `tests/conformance/test_async_tool_spec_adapter.py`.

- [x] Add failing regressions for unauthorized validator invocation and metadata-read exceptions.
- [x] Verify both fail on the previous implementation.
- [x] Check metadata inside a fail-closed exception boundary.
- [x] Check exact active-contract permission before invoking the validator.
- [x] Verify exact-head Python CI and dependency audit.

**Evidence:** PR #19 head `1320443749ae3dde52b2a1fb32421adc9a48642c`; Python CI #41119751437; dependency audit #41119751536. PR #19 remains open for independent review.

### Task 2: LangGraph version compatibility

**Files:** `.github/workflows/ci.yml`, `pyproject.toml`, `docs/CROSS_FRAMEWORK_CONFORMANCE.md`.

- [ ] Declare the tested optional LangGraph compatibility range.
- [ ] Run the same ToolNode conformance suite against the minimum declared version and a current supported version.
- [ ] Update the compatibility matrix with exact versions and CI evidence.
- [ ] Keep the adapter optional and the core package dependency-free.

### Task 3: Cross-platform persistence and reconciliation

**Files:** `.github/workflows/ci.yml`, `docs/PERSISTENCE_OPERATIONS.md`, `docs/RELEASE_READINESS.md`.

- [ ] Add targeted CI for Ubuntu, Windows, and macOS.
- [ ] Exercise event-chain append/verification, migration, backup/restore, multi-process claims, and reconciliation fault-injection tests.
- [ ] Preserve platform-specific failures as findings; do not weaken concurrency or integrity assertions to make a runner pass.
- [ ] Document that hosted-runner qualification is not a substitute for the user's production filesystem and backup target.

### Task 4: Reproducible dependency lock

**Files:** `uv.lock`, `pyproject.toml`, `.github/workflows/ci.yml`, `.github/workflows/security.yml`.

- [ ] Generate a lock covering the supported Python range and all declared extras.
- [ ] Commit the generated lockfile.
- [ ] Make CI verify the lock is current and install from the lock.
- [ ] Run the dependency audit against the locked environment.
- [ ] Review transitive license metadata before release.

### Task 5: Independent M6 label workflow

**Files:** `benchmarks/semantic_drift_review_template.csv`, `benchmarks/validate_semantic_labels.py`, `docs/SEMANTIC_DRIFT.md`.

- [ ] Provide a blinded two-reviewer annotation template with adjudication fields.
- [ ] Validate complete case coverage, allowed labels, reviewer disagreement, and provenance.
- [ ] Keep the existing 30-case labels marked provisional until independent reviewers complete the template.
- [ ] Do not invent reviewer identities or mark labels independent without actual review.

### Task 6: Completion and release evidence

**Files:** `docs/COMPLETION_LEDGER.md`, `docs/RELEASE_READINESS.md`, `README.md`, `CHANGELOG.md`.

- [x] Record verified merged/open PR state, exact-head CI, and the distinction between implementation and qualification.
- [ ] Refresh all documentation after Tasks 2–5.
- [ ] Keep license approval, independent review, branch protection, real provider qualification, and public release as owner/external gates.


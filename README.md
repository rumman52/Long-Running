# Intent Integrity for Long-Running AI Agents

A framework-neutral open-source project for detecting **intent drift** in long-running AI-agent workflows.

AI agents can continue following a plan after the evidence, assumptions, resource state, or approvals that justified it have changed. Intent Integrity provides a structured intent contract and a deterministic validation core to help integrations detect those changes before consequential actions.

## Project status

**Early development — Milestone 1: Intent Contract and Deterministic Validation Core.**

This project is not yet production-ready and does not claim compatibility with every agent framework. The initial core is designed to run without a model or network access.

## Design principles

- **Framework-neutral:** keep the contract and validation rules independent of any specific agent runtime.
- **Deterministic enforcement:** model output can propose or interpret a contract, but cannot override a failed validation decision.
- **Fail closed:** missing, revoked, expired, stale, invalidated, or unverifiable required conditions must not silently become permission to act.
- **Evidence-aware:** track evidence source, observation time, resource identity/version, and freshness.
- **Explicit outcomes:** distinguish `ALLOW`, `BLOCK`, and `REVALIDATION_REQUIRED`.
- **Honest reporting:** validation is not proof that an external action succeeded. Integrations must verify the resulting state separately.

## Initial architecture

1. **Intent contract** — goal, constraints, permitted/prohibited action categories, assumptions, approval requirements, and acceptance criteria.
2. **Evidence model** — source, timestamp, resource version, freshness policy, and invalidation state.
3. **Deterministic validator** — checks action eligibility, evidence freshness, contract version, and approval state.
4. **Integration adapters (later milestone)** — connect the core to controlled action boundaries in different agent environments.
5. **Evaluation suite (later milestone)** — reproducible tests for stale evidence, changed resources, revoked approvals, and failure cases.

## Quick start

Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

python -m pip install -e ".[dev]"
pytest
```

## Important limitation

A skill instruction or validator that is not placed at a trusted action boundary cannot force an arbitrary agent to comply. Effective enforcement requires the integration to route consequential tool calls through the validator and prevent bypasses. A pre-action check also cannot eliminate every race condition; the action adapter must use the strongest available conditional operation and verify the external result.

## License

License selection is pending review. Do not treat this repository as licensed for reuse until a license is added.

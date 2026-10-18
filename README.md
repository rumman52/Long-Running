# Intent Integrity for Long-Running AI Agents

A framework-neutral open-source project for detecting **intent drift** in long-running AI-agent workflows.

AI agents can continue following a plan after the evidence, assumptions, resource state, or approvals that justified it have changed. Intent Integrity provides a portable intent contract and a deterministic validation core to help integrations detect those changes before consequential actions.

## Project status

**Milestone 1 implementation is in place; early development, not production-ready.**

The current core has a JSON Schema, Python models, contract serialization, deterministic validation, automated tests, and CI. It does not yet include Gemma integration, persistent storage, an action gateway, or framework adapters.

## Core principles

- **Framework-neutral:** keep the contract and validation rules independent of a specific agent runtime.
- **Deterministic enforcement:** model output can propose or interpret a contract, but cannot override a failed validation decision.
- **Fail closed:** missing, revoked, expired, stale, invalidated, or unverifiable required conditions must not silently become permission to act.
- **Evidence-aware:** track evidence source, observation time, resource identity/version, and freshness.
- **Explicit outcomes:** distinguish ALLOW, BLOCK, and REVALIDATION_REQUIRED.
- **Honest reporting:** validation is not proof that an external action succeeded. Integrations must verify the resulting state separately.

## Current architecture

1. **Intent contract:** goal, constraints, permitted/prohibited action categories, consequential action categories, assumptions, per-action evidence/approval requirements, and acceptance criteria.
2. **Portable schema:** JSON Schema 2020-12 at [schemas/intent-contract.schema.json](schemas/intent-contract.schema.json).
3. **Deterministic validator:** checks action allowlists, evidence freshness, resource versions, contract version, and approval status.
4. **Contract serialization:** strict JSON mapping parser and serializer with schema-version checks.
5. **CI:** automated tests, Ruff checks, and mypy across Python 3.11, 3.12, and 3.13.

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
ruff check src tests examples
mypy src/intent_integrity
python examples/basic_validation.py
```

## Decision meanings

- **ALLOW:** all checks represented by the active contract and supplied trusted context passed.
- **BLOCK:** an explicit policy or authorization check failed.
- **REVALIDATION_REQUIRED:** required evidence or state must be refreshed before execution.

The validator performs no external actions. An integration must not execute an action for either BLOCK or REVALIDATION_REQUIRED.

## Important limitations

- Natural-language constraints and acceptance criteria are stored but are not semantically enforced by the current validator.
- The validator can only trust evidence and approvals supplied by trusted integration code; it does not independently authenticate providers yet.
- A pre-action check cannot eliminate every time-of-check/time-of-use race. Integrations should use conditional operations or provider-supported concurrency controls and verify the result.
- Arbitrary agents can bypass this core unless all relevant consequential tool calls are routed through a trusted enforcement boundary.
- Audit results are returned as structured data but are not yet persisted or tamper-evident.
- Gemma is not integrated yet. The core intentionally works without an LLM; an optional Gemma-based intent interpreter is planned after the contract and enforcement interfaces stabilize.

## License

License selection is pending maintainer approval. Until a license is added, do not assume this repository grants permission to reuse, modify, or redistribute its code.

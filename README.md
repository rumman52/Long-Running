# Intent Integrity

**A deterministic control layer for preserving authorized intent in long-running AI agents.**

[![Python CI](https://github.com/rumman52/Long-Running/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/rumman52/Long-Running/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB)

Intent Integrity is a framework-neutral Python project that helps a trusted application keep an AI agent aligned with an explicitly authorized goal while it plans, calls tools, pauses, resumes, and recovers from uncertain outcomes.

It turns important parts of that goal into a **versioned intent contract**, checks proposed actions against trusted evidence and approval state, records execution history, and provides recovery and external-outcome reconciliation primitives.

**The core principle is simple: the agent may propose an action; trusted code decides whether that action is allowed to proceed.**

> **Project maturity:** Early-stage, standalone framework-neutral Python library. M1–M5 core implementations and local tests are present; M6's 30-case provisional development corpus and bounded multi-trial evaluator are merged on main. The security candidate branch adds bounded MCP/guarded-tool input handling and a compiled LangGraph adversarial regression; exact-head CI has passed for the code-bearing candidate head; independent review and merge are still required. Live Gemma qualification, independent labels, live-provider qualification, deployment testing, maintainer license sign-off, and independent security review remain release gates. The library is not part of or dependent on any external agent runtime.

---

## Start here

- **New to the project?** Read [the architecture overview](docs/ARCHITECTURE.md).
- **Want to run it?** Follow [Quick start](#quick-start).
- **Want to understand the contract?** Read [the intent contract guide](docs/INTENT_CONTRACT.md).
- **Integrating an agent or tool?** Read [the runtime guide](docs/RUNTIME_GUIDE.md) and [guarded adapter guide](docs/MCP_ADAPTER.md).
- **Handling timeouts or duplicate external effects?** Read [external outcome reconciliation](docs/EXTERNAL_RECONCILIATION.md).
- **Operating SQLite state, backups, and retention?** Read [persistence operations](docs/PERSISTENCE_OPERATIONS.md).
- **Evaluating semantic drift?** Read [the optional semantic comparator guide](docs/SEMANTIC_DRIFT.md) and [benchmark methodology](docs/BENCHMARKS.md).
- **Reproducing tests and demos?** Follow [reproducible demos](docs/REPRODUCIBLE_DEMOS.md).
- **Preparing a release?** Review [release readiness](docs/RELEASE_READINESS.md).
- **Reviewing security boundaries?** Read [the threat model](docs/THREAT_MODEL.md) and [security policy](SECURITY.md).
- **Contributing or reporting a vulnerability?** Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
- **Checking what is complete?** Read [the roadmap](docs/ROADMAP.md).

## The problem

Long-running agents can start with a valid objective and still go wrong later:

- A constraint disappears after context compaction or a restart.
- A plan introduces an action the user never authorized.
- Evidence becomes stale after the plan was created.
- A consequential action proceeds without the required approval.
- A timeout hides whether an external write succeeded, so a retry creates a duplicate.
- An agent reports completion even though acceptance criteria are not supported by current evidence.

Ordinary conversation history is not a reliable authorization boundary. Intent Integrity provides structured state and deterministic checks around the agent. It does **not** assume that a model will always remember the original request or correctly judge its own behavior.

## How it works

The runtime is built around four responsibilities:

1. **Authorize** — a trusted host authenticates the user and creates the active intent contract.
2. **Evaluate** — the engine checks plans and proposed actions against the contract, current trusted context, evidence, and approvals.
3. **Control** — only an **ALLOW** decision may reach the guarded execution callback; the action is durably claimed before execution.
4. **Recover and reconcile** — the system verifies saved state, rebuilds compact context, and checks ambiguous external outcomes before any retry.

The model is not the authority for changing the contract, manufacturing evidence, granting approval, or declaring that an external side effect succeeded.

### Architecture at a glance

~~~mermaid
flowchart TD
    U[User goal] --> H[Trusted host authorizes request]
    H --> C[Versioned intent contract]
    A[AI agent] --> P[Proposed plan or action]
    C --> SM[Optional semantic comparator]
    P --> SM
    SM -. advisory findings only .-> HR[Optional human review]
    C --> D[Deterministic plan-drift checks]
    P --> D
    D --> V[Pre-action validator]
    C --> V
    E[Trusted evidence and approvals] --> V
    V -->|BLOCK / REVALIDATION_REQUIRED| S[Stop and correct or revalidate]
    V -->|ALLOW| K[Durable action claim]
    K --> X[Host-controlled executor]
    X --> O[Result or unknown outcome]
    O --> L[(SQLite event history)]
    C --> L
    L --> CP[Verified checkpoint]
    CP --> R[Recovery and compact context]
    L --> R
    R --> A
    O --> RC[External outcome reconciliation]
    RC --> L
~~~

The diagram shows the intended integration boundary. It does **not** mean that arbitrary agents are automatically intercepted. A host must route every consequential tool call through the guarded boundary; a separate unguarded route can bypass it. The optional semantic comparator is separate from the deterministic validator and cannot authorize actions or change validator decisions.

## What is implemented

| Capability | Current implementation |
|---|---|
| **Intent contract** | Typed, versioned goal and policy model; strict JSON serialization; JSON Schema; explicit, versioned contract amendments. |
| **Deterministic validation** | **ALLOW**, **BLOCK**, and **REVALIDATION_REQUIRED**; checks action categories, required evidence, evidence freshness and resource versions, contract version, and required approvals. |
| **Plan-drift checks** | Deterministic checks for prohibited or unauthorized action categories, missing dependencies, dependency cycles, uncovered acceptance criteria, and invalidated assumptions. |
| **Task history** | SQLite-backed ordered events, duplicate-event handling, per-task hash-chain verification, and checkpoint state-hash verification. |
| **Guarded execution** | A host-owned tool registry and callback gate. The action ID is claimed before execution; duplicate claims fail closed. |
| **Recovery and context reconstruction** | Restore the active authorized contract, verify checkpoint and event history, replay supported later events, detect invalidated assumptions, and rebuild compact context. |
| **Completion audit** | Compare acceptance criteria with current-plan step records and host-supplied evidence; unresolved action outcomes prevent a ready completion report. |
| **Semantic drift (M6)** | Optional provider-neutral semantic comparison with a Gemma/Ollama adapter, strict output validation, advisory-only findings, a 30-case provisional development dataset, and a 1–100 trial evaluator. Labels are not independently reviewed and live Gemma accuracy has not been measured. |
| **External outcome reconciliation (M5)** | Provider-neutral operation records, stable idempotency identity, conditional-version metadata, outcome lookup, and guarded retry after an authoritative **NOT_APPLIED** observation. |
| **Integration examples** | Runnable validation and long-running-task examples, a local reconciliation demo, a portable agent skill, and a minimal MCP stdio scaffold. |
| **Cross-framework adapters (M7)** | Optional structural async ToolSpec adapter and LangGraph ToolNode adapter, with local conformance tests. No external runtime dependency is required. |
| **Evaluation (M7)** | Reproducible unmonitored/deterministic/hybrid comparison with safety, recovery, latency, token-usage, and adapter-surface bypass metrics. Fixture mode is synthetic. |
| **Engineering checks** | Pytest, Ruff, mypy, official MCP SDK smoke conformance, LangGraph ToolNode conformance, M7 fixture evaluation, and a `pip-audit` workflow. CI supports Python 3.11–3.14; Python 3.15 is best-effort. |

These are implementation claims, not a claim that every integration or production threat has been qualified. The roadmap distinguishes implemented code from work that still needs broader testing or external evidence.

## Decision meanings

| Decision | Meaning | Expected host behavior |
|---|---|---|
| **ALLOW** | The checks represented by the validator passed for the supplied state at validation time. | The host may continue through the guarded execution path. |
| **BLOCK** | A policy or authorization requirement failed. | Do not execute the action. |
| **REVALIDATION_REQUIRED** | Evidence or contract state is missing, stale, invalidated, or out of date. | Refresh trusted state and validate again before proceeding. |

A **BLOCK** takes precedence over a revalidation warning. Missing evidence, missing approval, or an unknown external outcome must never be treated as permission to continue.

**Important:** **ALLOW** is not proof that an external operation succeeded, that the evidence source was honest, or that the overall task is complete.

## Quick start

### Requirements

- Python **3.11 or newer**
- Git, if cloning the repository
- Internet access to install the development dependencies

The package has no mandatory third-party runtime dependencies. The **dev** extra installs the test and quality-check tools.

### 1. Clone the repository

~~~bash
git clone https://github.com/rumman52/Long-Running.git
cd Long-Running
~~~

### 2. Create and activate a virtual environment

**Windows PowerShell**

~~~powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
~~~

If PowerShell blocks activation under your machine's execution policy, use the appropriate policy for your environment or activate the environment from Command Prompt instead.

**macOS / Linux**

~~~bash
python3.11 -m venv .venv
source .venv/bin/activate
~~~

### 3. Install the project

~~~bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
~~~

### 4. Run the examples

**Basic validation** — validates a sample action without executing it or contacting an external service:

~~~bash
python examples/basic_validation.py
~~~

**Long-running task** — demonstrates a local task, a blocked action without approval, assumption invalidation, checkpoint recovery, and a guarded callback:

~~~bash
python examples/long_running_task.py
~~~

**External outcome reconciliation** — demonstrates a lost response and outcome recovery using a local provider ledger:

~~~bash
python examples/external_reconciliation.py
~~~

**Optional semantic drift evaluation** — requires a local Ollama installation and a Gemma model. It reports labelled-set metrics and per-case output; it does not claim pre-measured accuracy:

~~~bash
ollama pull gemma3:4b
ollama serve
python examples/evaluate_semantic_drift.py --model gemma3:4b
~~~

See [Semantic Drift](docs/SEMANTIC_DRIFT.md) for the trust boundary, model setup, and metric definitions.

**MCP stdio scaffold** — starts a minimal newline-delimited JSON-RPC server. It is intended to be exercised by an MCP-capable client or a test harness, not as a standalone interactive demo:

~~~bash
python examples/guarded_mcp_server.py
~~~

The examples use local demonstration callbacks, temporary SQLite databases, or a local provider ledger. They do not publish a real report or qualify a live external service.

## Minimal validation example

This small example demonstrates the core API. It validates a permitted draft action; it does not execute that action.

~~~python
from datetime import UTC, datetime

from intent_integrity import (
    ActionRequest,
    IntentContract,
    ValidationContext,
    validate_action,
)

contract = IntentContract(
    contract_id="report-task",
    version=1,
    goal="Draft a report; do not publish without approval.",
    permitted_actions=("read_source", "write_report", "publish_report"),
    prohibited_actions=("delete_source",),
    consequential_actions=("publish_report",),
    required_approvals_by_action=(
        ("publish_report", ("publish-approval",)),
    ),
    acceptance_criteria=("Report is accurate",),
)

context = ValidationContext(
    now=datetime.now(UTC),
    evidence={},
    approvals={},
    active_contract_version=contract.version,
)

result = validate_action(
    contract,
    ActionRequest(action_id="draft-report", category="write_report"),
    context,
)

print(result.decision.value)  # ALLOW
~~~

For a full lifecycle, use **IntentIntegrityEngine** to record plans, execute guarded callbacks, checkpoint progress, recover after restart, and audit completion. For provider-aware external writes, use **ExternalActionCoordinator** with a provider implementation that satisfies the guarantees in the [reconciliation guide](docs/EXTERNAL_RECONCILIATION.md).

## Run the quality checks

From the activated virtual environment:

~~~bash
pytest
ruff check src tests examples benchmarks
mypy src/intent_integrity
~~~

The GitHub Actions workflow runs tests, examples, Ruff, and mypy on Python 3.11–3.14, plus a best-effort Python 3.15 job. Separate jobs exercise the official MCP Python SDK, LangGraph ToolNode conformance, M7 fixture evaluation, and dependency auditing. Check the live [CI workflow](https://github.com/rumman52/Long-Running/actions/workflows/ci.yml) for the current result; this README does not assert that an unobserved run has passed.

## Important safety and integration boundaries

Intent Integrity is a control component, not a complete security perimeter by itself.

- **The host must mediate every consequential tool.** Only registered and correctly routed tools are guarded. Any alternate unguarded route can bypass the checks.
- **The host owns identity and authorization.** The application must authenticate the user, authorize the initial contract and amendments, and supply trustworthy evidence and approval records. An authorization reference is audit metadata, not a cryptographic signature.
- **Model output is untrusted input.** A model, document, web page, or tool result must not be allowed to silently amend the active contract, fabricate verified evidence, or grant approval.
- **Unknown outcomes are not safe to retry blindly.** A callback can fail after an external service has already applied the effect. Reconcile the prior operation before retrying, and preserve the original operation identity.
- **Provider guarantees matter.** Safe reconciliation requires provider-side atomic idempotency, binding the key to the request, reliable outcome lookup, and enforcement of conditional writes/deadlines. The local tests do not qualify a real provider.
- **Time-of-check/time-of-use races remain possible.** A resource may change after validation. Use provider-supported conditional operations and resource-version checks at the write boundary.
- **Hash chains are tamper-evident, not tamper-proof.** Someone able to rewrite the whole database may be able to recompute the chain. Production systems need protected storage, access controls, backups, and potentially externally anchored signatures.
- **Evidence checks have a defined boundary.** The engine evaluates evidence metadata supplied by the host; it does not independently authenticate every evidence source or prove natural-language claims.
- **Semantic drift is not solved universally.** The optional M6 comparator can flag subtle deviations, but it can miss or hallucinate findings. It is advisory-only and has not been live-benchmarked here.

Read the [threat model](docs/THREAT_MODEL.md), [architecture](docs/ARCHITECTURE.md), and [runtime guide](docs/RUNTIME_GUIDE.md) before connecting tools that can change external systems.


## Cross-framework conformance and evaluation

Install the optional framework dependency and run adapter conformance tests:

~~~bash
python -m pip install -e ".[dev,langgraph]"
pytest tests/conformance -q
~~~

Run the deterministic fixture comparison:

~~~bash
python benchmarks/evaluate_m7.py --output artifacts/m7-evaluation.json
~~~

To measure the M6 semantic provider against the same M7 scenarios, install/run Ollama and a Gemma
model, then use:

~~~bash
python benchmarks/evaluate_m7.py --semantic-provider gemma-ollama --model gemma3:4b --output artifacts/m7-gemma-evaluation.json
~~~

The hybrid host policy maps a validated medium/high semantic review recommendation to a review pause
only after deterministic validation allows the action. The semantic layer itself never changes the
core validator decision. Fixture results are not model predictions; see
[Cross-Framework Conformance and Evaluation](docs/CROSS_FRAMEWORK_CONFORMANCE.md) for metrics and limitations.

## Current scope and roadmap

Milestones are not considered complete merely because a file or interface exists. The project tracks implementation separately from conformance, integration, and security evidence.

| Milestone | Status | What remains important |
|---|---|---|
| **M1 — Intent contract and deterministic validation** | Implemented in the repository | Verify the latest CI result before release. |
| **M2 — Runtime state, event history, checkpoints** | Persistence implementation and local multi-process tests added | Deployment-specific filesystem qualification; retention is documented, but automatic pruning is intentionally not implemented. |
| **M3 — Plan drift and recovery** | Deterministic recovery and bounded property-based tests added | Broader independent evaluation remains. |
| **M4 — Portable skill and guarded action boundary** | Portable skill, guarded adapter, MCP scaffold, official-SDK smoke test; bounded-input hardening is on a candidate branch | Independent review, full protocol/client matrix, and live host adversarial/bypass evaluation remain. |
| **M5 — External outcome reconciliation** | Provider-neutral coordinator and local fault-injection tests implemented | Live-provider adapters must be built and qualified against real provider guarantees. |
| **M6 — Semantic drift and optional Gemma adapter** | 30-case provisional development corpus and bounded multi-trial evaluator merged | Independent labels, held-out evaluation, and live Gemma measurements remain pending. |
| **M7 — Cross-framework conformance and evaluation** | Optional async ToolSpec and LangGraph ToolNode adapters, compatibility matrix, and synthetic harness added | Broader framework/version qualification and a reviewed model-backed hybrid run remain pending. |
| **M8 — Open-source release readiness** | Readiness baseline added on the integration branch | Maintainer license sign-off, independent external review, passing final CI, and a tagged release remain. |

See [docs/ROADMAP.md](docs/ROADMAP.md) for milestone acceptance criteria and the current checklist. The project does not claim universal drift detection, production readiness, or independently verified security.

## Repository map

~~~text
.
├── .github/
│   ├── dependabot.yml             # Dependency and Actions update proposals
│   └── workflows/
│       ├── ci.yml                 # Tests, type/lint checks, framework conformance, evaluation
│       └── security.yml           # pip-audit dependency audit
├── LICENSE                        # Apache-2.0 candidate; maintainer sign-off required
├── CONTRIBUTING.md                # Development and review requirements
├── SECURITY.md                    # Private-first vulnerability reporting
├── CHANGELOG.md                   # Unreleased M8 readiness changes
├── benchmarks/
│   ├── evaluate_m7.py
│   ├── m7_scenarios.json
│   └── semantic_drift_cases.json
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CROSS_FRAMEWORK_CONFORMANCE.md
│   ├── BENCHMARKS.md
│   ├── CROSS_FRAMEWORK_CONFORMANCE.md
│   ├── EXTERNAL_RECONCILIATION.md
│   ├── INTENT_CONTRACT.md
│   ├── MCP_ADAPTER.md
│   ├── PERSISTENCE_OPERATIONS.md
│   ├── RELEASE_READINESS.md
│   ├── REPRODUCIBLE_DEMOS.md
│   ├── ROADMAP.md
│   ├── RUNTIME_GUIDE.md
│   ├── SEMANTIC_DRIFT.md
│   └── THREAT_MODEL.md
├── examples/
├── schemas/intent-contract.schema.json
├── skills/intent-integrity/SKILL.md
├── src/intent_integrity/
│   ├── integrations/              # Optional host and LangGraph bridges
│   └── ...                        # Core validation, recovery, storage, and adapters
├── tests/
│   ├── conformance/
│   ├── test_mcp_sdk_conformance.py
│   ├── test_state_properties.py
│   ├── test_store_concurrency.py
│   └── test_store_operations.py
└── pyproject.toml
~~~

## License

An Apache-2.0 license candidate and matching package metadata are included on the M2–M8 integration branch. The maintainer must explicitly confirm that choice before tagging or publishing a release. Until the license choice is approved and merged, treat the project as unreleased and do not infer additional permissions from roadmap text.

---

**Project:** [rumman52/Long-Running](https://github.com/rumman52/Long-Running)  
**Package:** **intent-integrity**  
**Primary language:** Python  
**Design goal:** preserve authorized intent through explicit contracts, deterministic checks, durable state, and controlled recovery.

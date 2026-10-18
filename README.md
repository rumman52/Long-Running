# Intent Drift in Long-Running AI Agents

**Intent Integrity** is an open-source engineering project exploring how AI agents can stay faithful to a user's authorized goal during long-running tasks.

The idea is simple: an agent can make a good plan at the beginning and still lose track of the goal later. It might forget a requirement, act on old information, follow an instruction found in an untrusted document, or claim the task is finished before the required checks pass.

This project puts a **trusted intent and validation layer around an agent**. The layer keeps the task rules outside the agent's changing context and checks whether a proposed action is currently allowed.

> **Project status:** Milestone 1's core implementation is in place, but the project is still in early development and is not production-ready. The repository contains typed intent-contract models, serialization and JSON Schema validation, and a deterministic pre-action validator. The complete long-running monitor shown below is the target architecture; several integration and recovery components are still planned.

## Contents

- [The problem in plain English](#the-problem-in-plain-english)
- [What this project does](#what-this-project-does)
- [Architecture](#architecture)
- [How validation works today](#how-validation-works-today)
- [Decision meanings](#decision-meanings)
- [Example](#example)
- [Quick start](#quick-start)
- [What exists and what is planned](#what-exists-and-what-is-planned)
- [Repository structure](#repository-structure)
- [Design principles](#design-principles)
- [Limitations and security](#limitations-and-security)
- [Roadmap](#roadmap)
- [Documentation](#documentation)
- [License](#license)

## The problem in plain English

Imagine asking an AI agent:

> “Prepare a report using the latest verified data. Do not publish it until I approve the final version.”

The agent starts correctly. After many steps, it may use an old dataset, forget the approval requirement, or publish the report because a document it read said “publish now.”

That is a form of **intent drift**: the agent's later actions no longer reliably follow the user's authorized goal and rules.

Intent drift can look like:

- **Forgetting a constraint:** a requirement disappears after a long conversation or context compaction.
- **Using stale evidence:** an agent relies on a test result, file, approval, or resource state that has changed.
- **Scope creep:** the agent starts doing extra work the user did not authorize.
- **Following untrusted instructions:** text from a website, file, or tool result is mistakenly treated as permission to change the task.
- **Premature completion:** the agent says “done” without evidence that the required outcomes were achieved.
- **Ignoring an approval change:** an approval has expired, been revoked, or does not cover the proposed action.

A longer prompt can help an agent remember, but it is not a reliable enforcement mechanism on its own. The same model that forgets a requirement may also summarize it incorrectly. Important rules therefore need to live in a trusted layer outside the agent's working context.

## What this project does

The system is designed to:

1. **Record the authorized intent.** Store the goal, constraints, permitted and prohibited action categories, required evidence, approval rules, assumptions, and acceptance criteria in a structured contract.
2. **Check proposed actions.** Before a controlled action runs, validate it against the active contract and current trusted evidence.
3. **Return an explicit decision.** Say whether the action is allowed, blocked, or needs revalidation.
4. **Keep an audit trail.** The target architecture records the relevant plans, actions, evidence, decisions, and results so a long run can be inspected and replayed.
5. **Detect longer-term drift.** Future components will compare the task's progress with its authorized goal, including after restarts and context compaction.
6. **Recover safely.** Future recovery components will rebuild the agent's working context from the verified contract and checkpoint instead of inventing a new goal.

The current code implements the deterministic validation foundation. It does **not yet** provide a universal agent wrapper or automatically detect every semantic form of intent drift.

## Architecture

The diagram shows the **target system**, not a claim that every component is already implemented.

- **Blue nodes:** implemented core data models or validation behavior.
- **Grey dashed nodes:** planned components.
- **Green nodes:** the user, agent, or trusted host/integration responsibilities.

~~~mermaid
flowchart TD
    U["User / Authorized Goal Update"] --> HOST["Host application authenticates and authorizes the request"]
    HOST --> CONTRACT["Intent Contract<br/>Typed model and schema"]
    CONTRACT --> STORE[("Versioned Intent Store<br/>Planned")]

    AGENT["External AI Agent"] --> ADAPTER["Agent Adapter / Action Boundary<br/>Planned"]
    ADAPTER --> ACTION["ActionRequest"]
    ACTION --> VALIDATOR["Deterministic Pre-action Validator<br/>Implemented"]
    CONTRACT --> VALIDATOR
    TRUSTED["Trusted evidence, resource versions,<br/>and approval state"] --> CONTEXT["ValidationContext"]
    CONTEXT --> VALIDATOR

    VALIDATOR --> DECISION{"Validation decision"}
    DECISION -->|ALLOW| EXEC["Host may execute the action<br/>and verify its result"]
    DECISION -->|BLOCK| STOP["Stop: do not execute"]
    DECISION -->|REVALIDATION_REQUIRED| REFRESH["Refresh missing or outdated state,<br/>then validate again"]
    REFRESH --> CONTEXT

    EXEC --> NORMALIZER["Event Normalizer<br/>Planned"]
    NORMALIZER --> LEDGER[("Append-only Event Ledger<br/>Planned")]
    LEDGER --> MONITOR["Long-running Drift Monitor<br/>Planned"]
    CONTRACT --> MONITOR
    MONITOR --> DETECTOR["Drift Detector<br/>Planned monitor"]
    DETECTOR --> RULES["Deterministic validation rules<br/>Current foundation"]
    DETECTOR -.-> SEMANTIC["Semantic and trajectory analysis<br/>Planned"]
    RULES --> POLICY["Extended Policy and Recovery Layer<br/>Planned"]
    SEMANTIC --> POLICY
    POLICY -.-> RECOVERY["Recovery Manager and trusted checkpoints<br/>Planned"]
    RECOVERY -.-> PACKER["Rebuild a compact context from<br/>verified intent and progress"]
    PACKER -.-> AGENT
    POLICY --> EVAL["Evaluation, benchmarks, and metrics<br/>Planned"]

    classDef current fill:#eaf2ff,stroke:#2f6feb,stroke-width:2px,color:#111827;
    classDef planned fill:#f6f8fa,stroke:#8c959f,stroke-dasharray:5 5,color:#24292f;
    classDef external fill:#dafbe1,stroke:#1a7f37,color:#24292f;

    class CONTRACT,ACTION,CONTEXT,VALIDATOR,DECISION,RULES current;
    class STORE,ADAPTER,NORMALIZER,LEDGER,MONITOR,DETECTOR,SEMANTIC,POLICY,RECOVERY,PACKER,EVAL,REFRESH planned;
    class U,HOST,AGENT,TRUSTED,EXEC,STOP external;
~~~

### What each part means

| Component | Responsibility | Status |
|---|---|---|
| **Intent Contract** | A structured record of the goal and the rules that must remain in force. | Core model/schema exists |
| **Trusted host / integration** | Confirms who requested the task, authorizes contract changes, and supplies trusted evidence and approvals. | Integration responsibility |
| **Agent Adapter / Action Boundary** | Observes proposed actions and ensures controlled actions pass through validation. | Planned |
| **Deterministic Validator** | Checks action permissions, contract version, evidence freshness/resource version, and approval state. | Implemented |
| **Event Normalizer and Ledger** | Records what happened in a consistent, ordered, auditable format. | Planned |
| **Long-running Drift Monitor** | Reviews the contract and event history for changes in the agent's behavior or progress. | Planned |
| **Semantic / Trajectory Analysis** | Helps identify subtle scope changes, missing goals, or an increasingly irrelevant plan. | Planned |
| **Policy and Recovery Layer** | Decides whether to continue, stop, request fresh evidence, or re-anchor the agent. | Current validator has basic decisions; extended layer planned |
| **Checkpoints and Context Packer** | Preserve verified progress and restore the right context after a restart or compaction. | Planned |
| **Evaluation and Metrics** | Measures detection quality, false alarms, recovery, and runtime overhead. | Planned |

### The runtime flow we are building toward

1. A user gives the agent a task.
2. The trusted host turns the authorized request into an intent contract.
3. The agent proposes an action.
4. The integration sends the action, active contract, and trusted current evidence to the validator.
5. The validator returns a decision.
6. The integration executes the action only if the decision is **ALLOW**. If state is missing or outdated, it refreshes and validates again. If the action is blocked, it does not execute.
7. The future event ledger records the action and its result.
8. The future drift monitor periodically checks whether the overall run still follows the contract.
9. If context has drifted, the recovery layer will re-anchor the agent using the original authorized intent and verified progress.

**Important:** a pre-action check is effective only when the integration controls the action boundary. An agent that can call tools without going through the validator can bypass it.

## How validation works today

The current core is intentionally small, deterministic, and independent of a model API.

### 1. The host prepares a contract

An **IntentContract** can declare:

- a stable contract ID and version;
- the goal and declared constraints;
- permitted and prohibited action categories;
- which actions are consequential;
- required evidence and approvals for each action category;
- assumptions and their invalidation conditions;
- acceptance criteria for later outcome verification.

The host application must validate and authorize the contract before trusting it. A model's suggestion alone does not authorize a policy change.

### 2. The agent proposes an action

An **ActionRequest** contains an action ID and category. It does not get to decide which evidence or approvals are required. The validator resolves those requirements from the trusted contract.

### 3. The validator checks current state

The current validator can check:

- whether the action is explicitly prohibited or not on the permitted-action list;
- whether the contract version has changed;
- whether required evidence exists and is marked verified;
- whether evidence has a source and valid timestamp;
- whether evidence is stale under its configured freshness period;
- whether evidence was invalidated or refers to a different resource version;
- whether required approvals are present, approved, unexpired, and in scope.

A natural-language constraint is **not automatically enforceable just because it is written in the contract**. It must be translated into a machine-checkable rule or handled by a separately evaluated component.

### 4. The host follows the decision

The validator returns a structured result with a decision, reason codes, details, timestamp, action ID, and contract version. The host integration must honor that result.

The validator itself does not execute the action, call an external service, or verify that an external change succeeded.

## Decision meanings

The current validator has three outcomes:

| Decision | Plain-English meaning | Required response |
|---|---|---|
| **ALLOW** | All checks represented by the validator passed. | The trusted integration may proceed, subject to its own execution safeguards. |
| **BLOCK** | A known policy or approval rule failed. | Do not execute the action. |
| **REVALIDATION_REQUIRED** | Some required evidence or state is missing, stale, invalidated, unverifiable, or out of date. | Refresh the relevant state and validate again before execution. |

A **BLOCK** takes precedence over a revalidation warning. **REVALIDATION_REQUIRED** is **not** permission to proceed.

**ALLOW** does not mean “the whole task is complete” or “the external action succeeded.” It means only that the checks represented by this validator passed at validation time.

The broader target design may add decisions such as warning, re-anchoring, and human approval pauses. Those are not presented as implemented runtime features today.

## Example

Suppose a user asks an agent to merge a pull request only if the tests passed for the current commit and the required approval is still valid.

The contract says:

- merging is permitted;
- merging requires test evidence;
- the evidence must refer to the current commit;
- merging requires a valid approval;
- deleting the repository is prohibited.

Three possible outcomes:

- **Tests passed for the current commit and approval is valid:** the validator can return **ALLOW**.
- **The tests were run against an older commit:** the validator returns **REVALIDATION_REQUIRED**, so the host must refresh the evidence and check again.
- **The required approval is missing, expired, revoked, or outside its permitted scope:** the validator returns **BLOCK**.

The example in [examples/basic_validation.py](examples/basic_validation.py) demonstrates this kind of check. It only validates the action; it does not merge a pull request or call GitHub.

## Quick start

### Requirements

- Python 3.11 or newer
- Git, if you are cloning the repository

### Install

~~~bash
git clone https://github.com/rumman52/Long-Running.git
cd Long-Running

python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
~~~

### Run the example

~~~bash
python examples/basic_validation.py
~~~

The example prints the validation result. It does not execute the action.

### Run the tests and quality checks

~~~bash
pytest
ruff check src tests examples
mypy src/intent_integrity
~~~

The repository's GitHub Actions workflow is configured to run tests and code-quality checks on Python 3.11, 3.12, and 3.13. Check the [Actions page](https://github.com/rumman52/Long-Running/actions) for the actual result of each run.

## What exists and what is planned

### Implemented in the repository

- Typed, framework-neutral intent, action, evidence, approval, context, and result models.
- JSON serialization/deserialization helpers.
- A JSON Schema for the intent contract and schema-validation tests.
- A deterministic, side-effect-free pre-action validator.
- Explicit **ALLOW**, **BLOCK**, and **REVALIDATION_REQUIRED** decisions with reason codes.
- Unit tests for validation and serialization.
- A basic example and CI configuration.

### Not implemented yet

- A universal wrapper that automatically intercepts every agent's tool calls.
- An MCP or other framework-specific action adapter.
- A persistent, append-only event ledger.
- Automatic semantic or trajectory drift detection.
- Durable task checkpoints and restart recovery.
- Automatic re-anchoring after context compaction.
- A dashboard, hosted service, or built-in model client.
- A Gemma integration. The core is model-independent; an optional Gemma-based intent interpreter can be evaluated after the contract and enforcement interfaces stabilize.
- A completed benchmark proving that this approach outperforms alternatives.

These are planned engineering tasks, not existing capabilities. The project should add them in small steps and publish test and benchmark evidence as they become available.

## Repository structure

~~~text
Long-Running/
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── INTENT_CONTRACT.md
│   └── THREAT_MODEL.md
├── examples/
│   └── basic_validation.py
├── schemas/
│   └── intent-contract.schema.json
├── src/
│   └── intent_integrity/
│       ├── __init__.py
│       ├── models.py
│       ├── serialization.py
│       └── validator.py
├── tests/
│   ├── test_serialization.py
│   └── test_validator.py
├── pyproject.toml
└── README.md
~~~

## Design principles

- **Keep authority outside the model's working context.** The agent can propose plans, but cannot silently rewrite the authorized contract.
- **Use deterministic checks for enforceable rules.** Do not ask an LLM to decide whether a missing approval is acceptable.
- **Treat external content as data, not authority.** Instructions found in tool results, web pages, files, or model-generated summaries do not automatically change the user's intent.
- **Track evidence freshness.** A fact that was true earlier may no longer justify an action.
- **Preserve history.** Future event and checkpoint storage should make changes inspectable rather than silently overwriting prior decisions.
- **Make uncertainty visible.** Missing evidence is not proof that a condition is satisfied.
- **Measure before optimizing.** Evaluate tokens, latency, false alarms, and task success; fewer tokens are not useful if the agent loses important constraints.
- **Verify before claiming completion.** A success message is not a substitute for evidence.
- **Build and test incrementally.** Each milestone should have focused tests, reproducible examples, and documented limitations.

## Limitations and security

This project is an engineering prototype, not a security certification or a guarantee that all intent drift can be detected.

- The validator can enforce only rules represented in its structured inputs.
- A malicious or faulty adapter can provide incorrect evidence or approval state.
- If an agent can bypass the controlled action boundary, the validator cannot stop that bypass.
- A resource may change after validation but before execution. Integrations should use provider-supported conditional operations, version checks, compare-and-swap, or idempotency controls when available, and then verify the result.
- Current validation results are returned to the caller; they are not yet stored in a tamper-evident event ledger.
- Natural-language constraints and acceptance criteria are declarations unless mapped to explicit checks.
- Contract creation and amendments need an authenticated authorization process in the host application.

Read the [threat model](docs/THREAT_MODEL.md) before designing an integration that can affect external systems.

## Roadmap

The work is ordered to prove the foundation before adding complexity.

1. **Intent contract and deterministic core — current foundation.** Maintain typed models, schema validation, serialization, validation rules, and tests.
2. **Portable skill and integration contract.** Define how any agent can supply a proposed action and receive a validation decision without granting the agent control over policy.
3. **Controlled action boundary.** Build the first adapter, initially targeting an MCP integration, so consequential actions cannot silently bypass validation.
4. **Durable event history.** Add event sequencing, persistence, replay, and tests for duplicate events, stale state, and races.
5. **Long-run continuity and recovery.** Add trusted checkpoints and re-anchoring across context compaction and restarts.
6. **Semantic and trajectory evaluation.** Add optional model-assisted analysis, calibrated thresholds, and clear fallbacks when the evaluator is unavailable.
7. **Benchmark and hardening.** Compare unmonitored, deterministic-only, and hybrid approaches; measure detection quality, false blocks, recovery, task success, latency, and token overhead. Add a second adapter and a conformance suite.

Milestones should be marked complete only when their acceptance criteria have been tested. Do not claim universal detection or production readiness based on unit tests alone.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — current validation core and intended boundaries.
- [Intent Contract](docs/INTENT_CONTRACT.md) — contract fields, evidence freshness, and approval semantics.
- [Threat Model](docs/THREAT_MODEL.md) — threats, mitigations, and known gaps.
- [JSON Schema](schemas/intent-contract.schema.json) — machine-readable contract structure.
- [Basic Validation Example](examples/basic_validation.py) — runnable, side-effect-free example.
- [Tests](tests/) — validation and serialization test suites.

## License

A license has not yet been selected for this repository. Until a license file is added, do not assume that the code is licensed for reuse.

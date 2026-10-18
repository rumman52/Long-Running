# Architecture

## Objective

Preserve the host-authorized user goal across long-running agent work and prevent controlled actions from proceeding when the policy, evidence, or approval state does not justify them.

## Component boundaries

| Component | Responsibility | Status |
|---|---|---|
| Intent contract and schema | Versioned goal, constraints, allowed/prohibited actions, evidence and approval requirements, assumptions, acceptance criteria | Implemented |
| Deterministic validator | Returns ALLOW, BLOCK, or REVALIDATION_REQUIRED from trusted inputs | Implemented |
| Event model | Typed task events for plans, validation, action attempts, invalidation, and checkpoints | Implemented |
| SQLite event store | Per-task sequence, idempotent event append, hash-chain verification, checkpoint storage, action claims | Implemented initial adapter |
| Plan-drift detector | Checks action categories, dependency graph, acceptance-criteria coverage, invalidated assumptions, selected event patterns | Implemented deterministic checks |
| Runtime engine | Connects plan checks, validation, event persistence, guarded callback execution, checkpoint and recovery | Implemented scaffold |
| Compact context builder | Reconstructs the original goal, constraints, progress, verified facts, decisions, and recent events | Implemented |
| Trusted host and identity | Authenticates user, authorizes initial contract and amendments, provides trustworthy evidence/approval records | Integration responsibility |
| Agent action adapter | Intercepts every controlled tool call and maps provider state into trusted validation inputs | Not yet implemented |
| Optional semantic comparator | Provider-neutral structured comparison; optional Gemma/Ollama adapter; strict output validation and advisory findings | Implemented as opt-in utility; not wired into validator decisions |
| External outcome reconciler | Persists provider operations, looks up ambiguous outcomes, and guards retries with stable keys and version conditions | Provider-neutral implementation and local fault-injection tests; live adapters need qualification |
| Evaluation suite | Measures semantic precision/recall, false-pause and missed-drift rates, latency, and token overhead | Starter labelled dataset and harness implemented; live Gemma run pending |

## System flow

```mermaid
sequenceDiagram
    participant U as User
    participant H as Trusted Host
    participant A as AI Agent
    participant E as Intent Integrity Engine
    participant V as Deterministic Validator
    participant S as SQLite Event Store
    participant X as Host Executor

    U->>H: Authorized goal and constraints
    H->>E: Start task with authorized contract
    E->>S: Append TASK_STARTED
    A->>E: Submit plan
    E->>E: Check plan against contract
    E->>S: Append PLAN_RECORDED and drift report
    A->>E: Propose action
    E->>V: Contract + action + trusted current context
    V-->>E: ALLOW / BLOCK / REVALIDATION_REQUIRED
    E->>S: Append ACTION_VALIDATED
    alt Decision is not ALLOW
        E-->>A: Stop or request fresh evidence / approval
    else Decision is ALLOW
        E->>S: Claim action ID before execution
        E->>X: Execute callback
        X-->>E: Result or ambiguous exception
        E->>S: Record success or UNKNOWN outcome
    end
    E->>S: Save checkpoint and hash
    Note over E,S: After restart, verify ledger and checkpoint
    E->>S: Load checkpoint and events after checkpoint
    E->>E: Detect drift and rebuild compact context
    E-->>A: Re-anchored context plus recovery findings
```

## Trust and authorization

The host is the authority for who requested a task and which contract version is active. The engine pins the initial contract in the verified event history and compares each supplied contract with that active record. A different goal or policy at the same version is blocked. A legitimate change must use the explicit amendment operation, increment the version by exactly one, and carry a host/user authorization reference. The reference is audit metadata, not a cryptographic signature; the host must authenticate the authorizing person or system.

The agent may suggest a contract or plan, but model output alone must not activate a contract, remove a constraint, mark evidence verified, or grant approval. Trusted lifecycle events cannot be written through the generic observation-event API.

Evidence and approval state must be populated by authenticated integration code. The validator checks only the fields it receives; it cannot prove that a compromised adapter told the truth.

## Drift detection levels

1. **Deterministic policy checks:** implemented in the validator. Rejects prohibited or non-allowlisted action categories, missing/invalid approvals, stale or invalidated evidence, and contract-version mismatch.
2. **Plan-structure checks:** implemented in the drift detector. Finds unauthorized categories, missing dependencies, dependency cycles, unknown criteria, uncovered criteria, and invalidated assumptions.
3. **Event-trajectory checks:** initial deterministic rules inspect recorded invalidations and action-validation events.
4. **Semantic drift:** an optional provider-neutral comparator can compare the contract and plan using Gemma through Ollama. Its raw output is schema-validated and grounded to supplied text; findings are advisory only. It is not called by the deterministic validator and cannot grant permission, amend intent, or change an action decision. Live model measurements remain pending.

## Recovery semantics

Recovery verifies the task's event chain and the latest checkpoint hash. It restores the active authorized contract, replays later valid plan updates, step-completion records, and action decisions, and preserves verified facts and prior decisions from the checkpoint. A plan recorded against an older contract version blocks execution until a current plan is recorded. Invalidated assumptions create blocking drift findings; host-confirmed revalidation requires another plan before execution. The compact context explicitly says that external content and event payloads are records, not authority.

The checkpoint is a state snapshot, not a substitute for the event history. The history is retained so changes can be inspected.

## Action execution and duplicate prevention

The guarded execution path:
1. Validates the action against the current contract and trusted context.
2. Refuses to execute unless the result is ALLOW.
3. Claims the task/action ID in durable storage before invoking the callback.
4. Marks a successful callback as SUCCEEDED.
5. Marks an exception as UNKNOWN because the external side effect may have happened before the exception.
6. Refuses to claim the same action ID again.

This is an initial local safety primitive, not exactly-once execution across arbitrary providers. The host should use provider idempotency keys, conditional writes, and outcome reconciliation. A process crash after claiming but before recording a result leaves a claim that must be reconciled, not automatically retried.

## Storage and integrity

The SQLite adapter stores a monotonically sequenced event stream per task. Each event hash includes the prior event hash, so an edited or removed event is detectable when the chain is verified. Checkpoints have a separate SHA-256 state hash.

The hash chain is tamper-evident, not tamper-proof. Production use needs database access controls, backups, retention policies, operational monitoring, and potentially an externally anchored signature or write-once store.

## Key invariants

- The active contract is authorized outside the model.
- Only ALLOW passes the guarded execution gate.
- BLOCK takes precedence over revalidation.
- Missing or stale evidence is never treated as success.
- Consequential actions require valid scoped approvals.
- Reusing an action ID never invokes the executor twice through this gate.
- Ambiguous external outcomes fail closed.
- Untrusted content cannot amend intent or authorize actions.
- Completion claims must be backed by explicit acceptance evidence.

## Known gaps

No universal agent interception, qualified live-provider adapter, production identity layer, or production-qualified benchmark suite exists yet. The optional semantic comparator has a starter labelled dataset but has not been measured against a live Gemma model here. Provider-neutral external reconciliation is implemented; see [External Outcome Reconciliation](EXTERNAL_RECONCILIATION.md) for its trusted provider requirements and limits. Do not treat this scaffold as a production security guarantee.

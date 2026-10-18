# Runtime Guide

This guide explains the initial runtime scaffold. It is a local engineering demonstration, not a production deployment guide.

## 1. Install and run

Install the project and development dependencies as described in the repository README. Then run:

```bash
python examples/long_running_task.py
```

The example creates a temporary SQLite database, authorizes a sample contract in code, records a plan, checkpoints progress, demonstrates a blocked publication without approval, invalidates an assumption, recovers state, and demonstrates the approved path using a local callback.

The callback is only a demonstration. It does not connect to a real publishing service.

## 2. Use the engine

```python
from datetime import UTC, datetime

from intent_integrity import (
    ActionRequest,
    CheckpointState,
    IntentContract,
    IntentIntegrityEngine,
    SQLiteEventStore,
    ValidationContext,
)

contract = IntentContract(
    contract_id="task-123",
    version=1,
    goal="Prepare a report without publishing before approval",
    permitted_actions=("read_source", "write_report", "publish_report"),
    prohibited_actions=("delete_source",),
    consequential_actions=("publish_report",),
    required_approvals_by_action=(("publish_report", ("publish-approval",)),),
    acceptance_criteria=("Report is accurate",),
)

with SQLiteEventStore("intent-ledger.sqlite3") as store:
    engine = IntentIntegrityEngine(store)
    engine.start_task(contract)

    context = ValidationContext(
        now=datetime.now(UTC),
        evidence={},
        approvals={},
        active_contract_version=contract.version,
    )
    result = engine.guarded_execute(
        contract,
        ActionRequest("write-report-step-1", "write_report"),
        context,
        executor=lambda: {"saved": True},
    )
    assert result.validation.decision.value == "ALLOW"
    assert result.executed
```

The host must authenticate the user and authorize the contract before calling `start_task`. The example omits that application-specific identity layer.

## 3. Contract and action IDs

- `contract_id` identifies a task and is used as the task ID by the initial engine.
- Increment `version` when the authorized contract changes.
- Use stable, unique action IDs for individual intended side effects.
- Never create a new action ID merely to retry an ambiguous action. First reconcile the prior attempt with the provider.
- Populate evidence and approval context from trusted integration code, not from model-generated claims.

## 4. Decisions

- `ALLOW`: checks represented in the contract passed at validation time.
- `BLOCK`: policy or authorization failed.
- `REVALIDATION_REQUIRED`: evidence or active contract state must be refreshed and checked again.

The engine will not call the executor unless the validator returns ALLOW. It claims the action ID before calling the executor. A duplicate ID raises `ActionAlreadyClaimed`. If the callback raises an exception, the action is marked `UNKNOWN`, because the external effect may have happened even if the caller did not receive a successful response.

## 5. Recovery

Create a `CheckpointState` containing the authorized contract, plan, completed step IDs, completed acceptance criteria, verified facts, and prior decisions. Facts must be explicitly marked `verified: True`. Call `engine.checkpoint(state)` to persist the snapshot.

After restart, call `engine.recover(task_id)`. Recovery:
1. verifies the event hash chain;
2. loads and verifies the latest checkpoint;
3. reconstructs the typed state;
4. reads events after the checkpoint sequence;
5. detects invalidated assumptions and selected event-level drift;
6. returns a compact context anchored to the original intent.

A recovery bundle can report blocking drift. The host must stop or replan when blocking drift exists; this scaffold does not autonomously choose a new authorized goal.

## 6. Operational cautions

- All consequential actions must be routed through a trusted action boundary.
- The SQLite adapter is a starter implementation; validate concurrent writers and crash behavior before production use.
- Hash verification detects changes to the recorded chain, but cannot prevent an attacker with full database control from rewriting and rehashing the entire database.
- Provider-specific idempotency and outcome reconciliation are not included.
- Natural-language constraints are not automatically enforceable.
- Semantic plan comparison is not included; current drift checks are deterministic and structural.
- Do not expose the database or approval state to untrusted model-controlled tools.

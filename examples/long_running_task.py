"""Runnable example of intent preservation across a checkpoint and restart."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from intent_integrity import (
    ActionRequest,
    Approval,
    Assumption,
    ApprovalStatus,
    CheckpointState,
    EventType,
    IntentContract,
    IntentIntegrityEngine,
    PlanStep,
    SQLiteEventStore,
    ValidationContext,
)


def main() -> None:
    now = datetime.now(UTC)
    contract = IntentContract(
        contract_id="example-report-task",
        version=1,
        goal="Prepare an accurate report; do not publish until the user approves it.",
        assumptions=(
            Assumption(
                "source-current",
                "The source data remains current",
                evidence_ids=("source-snapshot",),
            ),
        ),
        constraints=("Keep the report within the requested scope",),
        permitted_actions=("read_source", "write_report", "publish_report"),
        prohibited_actions=("delete_source",),
        consequential_actions=("publish_report",),
        required_approvals_by_action=(("publish_report", ("publish-approval",)),),
        acceptance_criteria=("Report is accurate", "User approves final report"),
    )
    plan = (
        PlanStep(
            "draft",
            "Read verified source data and draft the report",
            "write_report",
            acceptance_criteria=("Report is accurate",),
        ),
        PlanStep(
            "publish",
            "Publish only after the user approves the final report",
            "publish_report",
            acceptance_criteria=("User approves final report",),
            dependencies=("draft",),
        ),
    )

    with TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "intent-ledger.sqlite3"
        with SQLiteEventStore(database_path) as store:
            engine = IntentIntegrityEngine(store)
            engine.start_task(contract)
            drift = engine.record_plan(contract, plan)
            if drift.has_blocking_drift:
                raise RuntimeError(f"Plan contains blocking drift: {drift.to_dict()}")

            state = CheckpointState(
                task_id=contract.contract_id,
                contract=contract,
                plan=plan,
                completed_step_ids=("draft",),
                completed_criteria=("Report is accurate",),
                verified_facts=(
                    {"fact": "Source snapshot was verified by the host", "verified": True},
                ),
            )
            engine.checkpoint(state)

            context = ValidationContext(
                now=now,
                approvals={},
                evidence={},
                active_contract_version=contract.version,
            )
            blocked = engine.guarded_execute(
                contract,
                ActionRequest("publish-before-approval", "publish_report"),
                context,
                lambda: "This must never run",
            )
            print("Publish without approval:", blocked.validation.decision.value)
            print("Was external action executed:", blocked.executed)

            engine.record_event(
                contract.contract_id,
                EventType.ASSUMPTION_INVALIDATED,
                {"assumption_id": "source-current", "reason": "source changed"},
            )
            recovered = engine.recover(contract.contract_id)
            print("Recovered goal:", recovered.state.contract.goal)
            print("Blocking drift found:", recovered.drift_report.has_blocking_drift)
            print("Compact context characters:", len(recovered.compact_context))

            # In a real host, verify this evidence with its source before recording revalidation.
            engine.revalidate_assumption(
                contract, "source-current", evidence_ids=("source-snapshot",)
            )
            engine.record_plan(contract, plan)

            approved = Approval(
                "publish-approval",
                ApprovalStatus.APPROVED,
                expires_at=now + timedelta(minutes=5),
                allowed_actions=("publish_report",),
            )
            approved_context = ValidationContext(
                now=now,
                approvals={"publish-approval": approved},
                evidence={},
                active_contract_version=contract.version,
            )
            publish_result = engine.guarded_execute(
                contract,
                ActionRequest("publish-after-approval", "publish_report"),
                approved_context,
                lambda: "published by example callback",
            )
            print("Publish after approval:", publish_result.validation.decision.value)
            print("Was external action executed:", publish_result.executed)


if __name__ == "__main__":
    main()

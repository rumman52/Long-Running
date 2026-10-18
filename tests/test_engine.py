from datetime import UTC, datetime, timedelta

import pytest

from intent_integrity import (
    ActionAlreadyClaimed,
    ActionRequest,
    ActionStatus,
    Approval,
    ApprovalStatus,
    Assumption,
    CheckpointState,
    Decision,
    EventType,
    IntentContract,
    IntentIntegrityEngine,
    PlanStep,
    SQLiteEventStore,
    ValidationContext,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def make_contract() -> IntentContract:
    return IntentContract(
        contract_id="task-engine",
        version=1,
        goal="Prepare an accurate report and do not publish without approval",
        constraints=("Preserve the original scope", "Do not publish without approval"),
        permitted_actions=("read_source", "write_report", "publish_report"),
        prohibited_actions=("delete_source",),
        consequential_actions=("publish_report",),
        required_approvals_by_action=(("publish_report", ("publish-approval",)),),
        assumptions=(Assumption("source-current", "The source data is current"),),
        acceptance_criteria=("Report is accurate",),
    )


def make_context(*, approvals: dict[str, Approval] | None = None) -> ValidationContext:
    return ValidationContext(
        now=NOW,
        evidence={},
        approvals=approvals or {},
        active_contract_version=1,
    )


def test_guarded_execute_never_calls_executor_when_blocked() -> None:
    contract = make_contract()
    with SQLiteEventStore(":memory:") as store:
        engine = IntentIntegrityEngine(store, clock=lambda: NOW)
        engine.start_task(contract)
        calls: list[str] = []
        result = engine.guarded_execute(
            contract,
            ActionRequest("publish-1", "publish_report"),
            make_context(),
            lambda: calls.append("executed"),
        )
        assert result.validation.decision == Decision.BLOCK
        assert not result.executed
        assert calls == []


def test_guarded_execute_claims_action_and_prevents_duplicate_execution() -> None:
    contract = make_contract()
    approval = Approval(
        "publish-approval",
        ApprovalStatus.APPROVED,
        expires_at=NOW + timedelta(minutes=5),
        allowed_actions=("publish_report",),
    )
    with SQLiteEventStore(":memory:") as store:
        engine = IntentIntegrityEngine(store, clock=lambda: NOW)
        engine.start_task(contract)
        calls: list[str] = []
        action = ActionRequest("write-1", "write_report")
        result = engine.guarded_execute(
            contract, action, make_context(), lambda: calls.append("saved")
        )
        assert result.validation.decision == Decision.ALLOW
        assert result.executed
        assert calls == ["saved"]
        with pytest.raises(ActionAlreadyClaimed):
            engine.guarded_execute(
                contract,
                action,
                make_context(approvals={"publish-approval": approval}),
                lambda: calls.append("duplicated"),
            )
        assert calls == ["saved"]


def test_executor_exception_is_unknown_and_not_retried() -> None:
    contract = make_contract()
    with SQLiteEventStore(":memory:") as store:
        engine = IntentIntegrityEngine(store, clock=lambda: NOW)
        engine.start_task(contract)
        action = ActionRequest("write-timeout", "write_report")

        def timeout() -> object:
            raise TimeoutError("external result may be ambiguous")

        result = engine.guarded_execute(contract, action, make_context(), timeout)
        assert result.outcome_unknown
        assert result.error_type == "TimeoutError"
        record = store.get_action_record(contract.contract_id, action.action_id)
        assert record is not None
        assert record.status == ActionStatus.UNKNOWN
        with pytest.raises(ActionAlreadyClaimed):
            engine.guarded_execute(contract, action, make_context(), lambda: "retry")


def test_checkpoint_recovery_preserves_intent_and_detects_drift() -> None:
    contract = make_contract()
    plan = (
        PlanStep(
            "draft",
            "Read source and draft the report",
            "write_report",
            acceptance_criteria=("Report is accurate",),
        ),
    )
    state = CheckpointState(
        task_id=contract.contract_id,
        contract=contract,
        plan=plan,
        verified_facts=({"fact": "Source snapshot 42 is verified", "verified": True},),
    )
    with SQLiteEventStore(":memory:") as store:
        engine = IntentIntegrityEngine(store, clock=lambda: NOW)
        engine.start_task(contract)
        engine.record_plan(contract, plan)
        engine.checkpoint(state)
        engine.record_event(
            contract.contract_id,
            EventType.ASSUMPTION_INVALIDATED,
            {"assumption_id": "source-current", "reason": "source version changed"},
        )
        recovered = engine.recover(contract.contract_id)
        assert recovered.state.contract.goal == contract.goal
        assert recovered.state.contract.constraints == contract.constraints
        assert recovered.state.verified_facts[0]["verified"] is True
        assert recovered.drift_report.has_blocking_drift
        assert "original_goal" in recovered.compact_context
        assert "Do not publish without approval" in recovered.compact_context
        assert len(recovered.replay_events) >= 2


def test_checkpoint_rejects_unverified_facts() -> None:
    contract = make_contract()
    with pytest.raises(ValueError, match="explicitly marked verified"):
        CheckpointState(
            task_id=contract.contract_id,
            contract=contract,
            verified_facts=({"fact": "unverified tool output", "verified": False},),
        )

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from intent_integrity import (
    ActionRequest,
    Evidence,
    EventType,
    IntentContract,
    IntentIntegrityEngine,
    PlanStep,
    SQLiteEventStore,
    ValidationContext,
)

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


def _setup(engine: IntentIntegrityEngine) -> IntentContract:
    contract = IntentContract(
        contract_id="report", version=1, goal="Create a verified report",
        permitted_actions=("write",), acceptance_criteria=("accurate", "readable"),
    )
    engine.start_task(contract)
    engine.record_plan(contract, (
        PlanStep("draft", "Draft report", "write", ("accurate",)),
        PlanStep("review", "Review report", "write", ("readable",), ("draft",)),
    ))
    return contract


def _evidence() -> dict[str, Evidence]:
    return {
        "source": Evidence("source", "host-verified-source", NOW, freshness_ttl_seconds=60),
        "review": Evidence("review", "host-verified-review", NOW, freshness_ttl_seconds=60),
    }


def test_completion_requires_current_criteria_and_fresh_evidence() -> None:
    with SQLiteEventStore(":memory:") as store:
        engine = IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = _setup(engine)
        assert "ACCEPTANCE_CRITERION_INCOMPLETE" in engine.complete_task(
            contract, evidence=_evidence(), now=NOW
        ).reason_codes
        engine.record_step_completed(contract, "draft", completed_criteria=("accurate",),
                                     evidence_ids=("source",))
        engine.record_step_completed(contract, "review", completed_criteria=("readable",),
                                     evidence_ids=("review",))
        stale = engine.verify_completion(contract, evidence=_evidence(),
                                         now=NOW + timedelta(seconds=61))
        assert not stale.ready and "EVIDENCE_STALE" in stale.reason_codes
        assert not engine.verify_completion(contract, evidence={"source": _evidence()["source"]},
                                            now=NOW).ready
        ready = engine.complete_task(contract, evidence=_evidence(), now=NOW)
        assert ready.ready
        assert ready.evidence_by_criterion == {"accurate": ("source",), "readable": ("review",)}
        assert len([e for e in store.list_events("report")
                    if e.event.event_type == EventType.TASK_COMPLETED]) == 1


def test_completion_does_not_trust_old_plan_or_unknown_action() -> None:
    with SQLiteEventStore(":memory:") as store:
        engine = IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = _setup(engine)
        engine.record_step_completed(contract, "draft", completed_criteria=("accurate",),
                                     evidence_ids=("source",))
        engine.record_step_completed(contract, "review", completed_criteria=("readable",),
                                     evidence_ids=("review",))
        engine.record_plan(contract, (
            PlanStep("draft", "New draft", "write", ("accurate",)),
            PlanStep("review", "New review", "write", ("readable",), ("draft",)),
        ))
        assert "ACCEPTANCE_CRITERION_INCOMPLETE" in engine.verify_completion(
            contract, evidence=_evidence(), now=NOW
        ).reason_codes
        engine.record_step_completed(contract, "draft", completed_criteria=("accurate",),
                                     evidence_ids=("source",))
        engine.record_step_completed(contract, "review", completed_criteria=("readable",),
                                     evidence_ids=("review",))

        def timeout() -> None:
            raise TimeoutError("outcome unknown")

        engine.guarded_execute(contract, ActionRequest("ambiguous", "write"),
                               ValidationContext(NOW, active_contract_version=1), timeout)
        assert "ACTION_OUTCOME_UNRESOLVED" in engine.verify_completion(
            contract, evidence=_evidence(), now=NOW
        ).reason_codes
        amended = replace(contract, version=2)
        engine.amend_contract(contract, amended, authorization_ref="user-confirmed-update")
        assert not engine.verify_completion(amended, evidence=_evidence(), now=NOW).ready

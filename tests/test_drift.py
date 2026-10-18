from intent_integrity import (
    Assumption,
    DriftSeverity,
    IntentContract,
    PlanStep,
    detect_plan_drift,
)


def make_contract() -> IntentContract:
    return IntentContract(
        contract_id="task-drift",
        version=1,
        goal="Produce an accurate report for user review",
        constraints=("Do not publish before approval",),
        permitted_actions=("read_source", "write_report", "publish_report"),
        prohibited_actions=("delete_source",),
        consequential_actions=("publish_report",),
        assumptions=(Assumption("source-current", "The source data remains current"),),
        acceptance_criteria=("Report is accurate", "User approves final report"),
    )


def test_unauthorized_plan_action_is_blocking() -> None:
    report = detect_plan_drift(
        make_contract(),
        [PlanStep("step-1", "Delete source data", "delete_source")],
    )
    assert report.has_blocking_drift
    assert any(signal.code == "PROHIBITED_PLAN_ACTION" for signal in report.signals)


def test_uncovered_acceptance_criteria_warn() -> None:
    report = detect_plan_drift(
        make_contract(),
        [PlanStep("step-1", "Read data and draft report", "write_report", ("Report is accurate",))],
    )
    assert not report.has_blocking_drift
    assert any(
        signal.code == "ACCEPTANCE_CRITERION_UNCOVERED"
        and signal.severity == DriftSeverity.WARNING
        for signal in report.signals
    )


def test_dependency_cycle_is_blocking() -> None:
    report = detect_plan_drift(
        make_contract(),
        [
            PlanStep("step-1", "Read source", "read_source", dependencies=("step-2",)),
            PlanStep("step-2", "Write report", "write_report", dependencies=("step-1",)),
        ],
    )
    assert any(signal.code == "PLAN_DEPENDENCY_CYCLE" for signal in report.signals)


def test_invalidated_assumption_requires_replanning() -> None:
    report = detect_plan_drift(
        make_contract(),
        [],
        invalidated_assumptions=("source-current",),
    )
    assert report.has_blocking_drift
    assert any(signal.code == "ASSUMPTION_INVALIDATED" for signal in report.signals)

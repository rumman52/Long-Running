"""Deterministic plan and trajectory checks for intent drift."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from intent_integrity.events import EventType, StoredEvent
from intent_integrity.models import IntentContract


class DriftSeverity(StrEnum):
    """Impact level assigned to a detected deviation."""

    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


@dataclass(frozen=True, slots=True)
class PlanStep:
    """A plan step explicitly mapped to an allowed action and acceptance criteria."""

    step_id: str
    description: str
    action_category: str
    acceptance_criteria: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DriftSignal:
    """One explainable, deterministic drift finding."""

    code: str
    severity: DriftSeverity
    message: str
    step_id: str | None = None


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Drift findings for a plan and the recent event trajectory."""

    contract_id: str
    contract_version: int
    signals: tuple[DriftSignal, ...]

    @property
    def has_blocking_drift(self) -> bool:
        """Whether at least one finding requires the run to stop for review."""
        return any(signal.severity == DriftSeverity.BLOCKING for signal in self.signals)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible report."""
        return {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "has_blocking_drift": self.has_blocking_drift,
            "signals": [
                {
                    "code": signal.code,
                    "severity": signal.severity.value,
                    "message": signal.message,
                    "step_id": signal.step_id,
                }
                for signal in self.signals
            ],
        }


def _has_dependency_cycle(steps: dict[str, PlanStep]) -> bool:
    state: dict[str, int] = {}

    def visit(step_id: str) -> bool:
        marker = state.get(step_id, 0)
        if marker == 1:
            return True
        if marker == 2:
            return False
        state[step_id] = 1
        for dependency in steps[step_id].dependencies:
            if dependency in steps and visit(dependency):
                return True
        state[step_id] = 2
        return False

    return any(visit(step_id) for step_id in steps if state.get(step_id, 0) == 0)


def detect_plan_drift(
    contract: IntentContract,
    plan: Iterable[PlanStep],
    *,
    completed_criteria: Iterable[str] = (),
    invalidated_assumptions: Iterable[str] = (),
    events: Iterable[StoredEvent] = (),
) -> DriftReport:
    """Compare a plan and recent event history with the authorized contract.

    This detector is deliberately deterministic. It detects structural and policy drift;
    it does not claim to understand arbitrary natural-language intent semantically.
    """
    plan_steps = tuple(plan)
    completed = set(completed_criteria)
    invalidated = set(invalidated_assumptions)
    criteria = set(contract.acceptance_criteria)
    assumption_ids = {assumption.assumption_id for assumption in contract.assumptions}
    signals: list[DriftSignal] = []

    def add(code: str, severity: DriftSeverity, message: str, step_id: str | None = None) -> None:
        signal = DriftSignal(code, severity, message, step_id)
        if signal not in signals:
            signals.append(signal)

    counts: dict[str, int] = {}
    for step in plan_steps:
        counts[step.step_id] = counts.get(step.step_id, 0) + 1
    for step_id, count in counts.items():
        if not step_id.strip() or count > 1:
            add(
                "DUPLICATE_OR_EMPTY_STEP_ID",
                DriftSeverity.BLOCKING,
                f"Plan step ID {step_id!r} is empty or appears more than once.",
                step_id or None,
            )

    steps_by_id = {step.step_id: step for step in plan_steps if step.step_id.strip()}
    for step in plan_steps:
        if not step.description.strip():
            add(
                "EMPTY_PLAN_STEP",
                DriftSeverity.WARNING,
                "A plan step has no useful description.",
                step.step_id,
            )
        if step.action_category in contract.prohibited_actions:
            add(
                "PROHIBITED_PLAN_ACTION",
                DriftSeverity.BLOCKING,
                f"Step proposes prohibited action category {step.action_category!r}.",
                step.step_id,
            )
        elif step.action_category not in contract.permitted_actions:
            add(
                "UNAUTHORIZED_PLAN_ACTION",
                DriftSeverity.BLOCKING,
                f"Step action category {step.action_category!r} is not permitted by the contract.",
                step.step_id,
            )
        for criterion in step.acceptance_criteria:
            if criterion not in criteria:
                add(
                    "UNKNOWN_ACCEPTANCE_CRITERION",
                    DriftSeverity.BLOCKING,
                    f"Step references a criterion not present in the contract: {criterion!r}.",
                    step.step_id,
                )
        for dependency in step.dependencies:
            if dependency not in steps_by_id:
                add(
                    "MISSING_PLAN_DEPENDENCY",
                    DriftSeverity.BLOCKING,
                    f"Dependency {dependency!r} does not exist in the plan.",
                    step.step_id,
                )

    if _has_dependency_cycle(steps_by_id):
        add(
            "PLAN_DEPENDENCY_CYCLE",
            DriftSeverity.BLOCKING,
            "Plan dependencies contain a cycle, so the execution order is not well-defined.",
        )

    covered = {
        criterion
        for step in plan_steps
        for criterion in step.acceptance_criteria
        if criterion in criteria
    }
    unknown_completed = completed - criteria
    for criterion in sorted(unknown_completed):
        add(
            "UNKNOWN_COMPLETED_CRITERION",
            DriftSeverity.WARNING,
            f"Progress claims completion of an unknown criterion: {criterion!r}.",
        )
    for criterion in sorted(criteria - covered - completed):
        add(
            "ACCEPTANCE_CRITERION_UNCOVERED",
            DriftSeverity.WARNING,
            f"No planned step or recorded completion covers criterion {criterion!r}.",
        )

    for assumption_id in sorted(invalidated):
        if assumption_id in assumption_ids:
            add(
                "ASSUMPTION_INVALIDATED",
                DriftSeverity.BLOCKING,
                f"Assumption {assumption_id!r} was invalidated; the plan needs revalidation.",
            )
        else:
            add(
                "UNKNOWN_INVALIDATED_ASSUMPTION",
                DriftSeverity.WARNING,
                f"An event references unknown assumption {assumption_id!r}.",
            )

    for stored in events:
        event = stored.event
        if event.event_type == EventType.ASSUMPTION_INVALIDATED:
            assumption_id = event.payload.get("assumption_id")
            if isinstance(assumption_id, str) and assumption_id in assumption_ids:
                add(
                    "ASSUMPTION_INVALIDATED",
                    DriftSeverity.BLOCKING,
                    f"Assumption {assumption_id!r} was invalidated in the event history.",
                )
        elif event.event_type == EventType.ACTION_VALIDATED:
            category = event.payload.get("category")
            decision = event.payload.get("decision")
            if isinstance(category, str) and (
                category in contract.prohibited_actions
                or category not in contract.permitted_actions
            ):
                add(
                    "UNAUTHORIZED_ACTION_ATTEMPT",
                    DriftSeverity.BLOCKING,
                    f"Event history contains an attempted unauthorized action: {category!r}.",
                )
            if isinstance(decision, str) and decision != "ALLOW":
                add(
                    "ACTION_REQUIRES_INTERVENTION",
                    DriftSeverity.WARNING,
                    f"An action was validated with decision {decision!r}.",
                )

    return DriftReport(contract.contract_id, contract.version, tuple(signals))

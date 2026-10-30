"""Small, reproducible evaluation harness for advisory semantic drift detection."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from statistics import fmean

from intent_integrity.drift import PlanStep
from intent_integrity.models import Assumption, IntentContract
from intent_integrity.semantic import (
    SemanticComparisonRequest,
    SemanticDriftProvider,
    SemanticDriftResult,
    SemanticStatus,
    analyze_semantic_drift,
)


@dataclass(frozen=True, slots=True)
class SemanticEvaluationCase:
    """One labelled benchmark example. Labels must be reviewed by humans."""

    case_id: str
    request: SemanticComparisonRequest
    expected_drift: bool


@dataclass(frozen=True, slots=True)
class SemanticEvaluationMetrics:
    """Aggregate classification, latency, and token-overhead measurements."""

    case_count: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    false_pause_rate: float | None
    missed_drift_rate: float | None
    mean_latency_ms: float
    p95_latency_ms: float
    prompt_tokens_total: int
    completion_tokens_total: int
    token_usage_cases: int
    average_total_tokens_per_measured_case: float | None
    status_counts: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "case_count": self.case_count,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "false_pause_rate": self.false_pause_rate,
            "missed_drift_rate": self.missed_drift_rate,
            "mean_latency_ms": round(self.mean_latency_ms, 3),
            "p95_latency_ms": round(self.p95_latency_ms, 3),
            "prompt_tokens_total": self.prompt_tokens_total,
            "completion_tokens_total": self.completion_tokens_total,
            "token_usage_cases": self.token_usage_cases,
            "average_total_tokens_per_measured_case": (
                round(self.average_total_tokens_per_measured_case, 3)
                if self.average_total_tokens_per_measured_case is not None
                else None
            ),
            "status_counts": dict(self.status_counts),
            "review_threshold": "medium or high validated finding",
            "note": (
                "A review recommendation is advisory only. Unavailable, refused, uncertain, "
                "and invalid outputs do not recommend review and are counted as no detection."
            ),
        }


def _object(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a JSON object with string keys")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return tuple(value)


def _integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def load_semantic_evaluation_cases(
    path: Path,
) -> tuple[str, tuple[SemanticEvaluationCase, ...]]:
    """Load and validate a labelled semantic-evaluation dataset."""
    document = _object(json.loads(path.read_text(encoding="utf-8")), "dataset")
    if _integer(document.get("version"), "version") != 1:
        raise ValueError("unsupported benchmark dataset version")
    labeling_policy = _string(document.get("labeling_policy"), "labeling_policy")
    contract_data = _object(document.get("contract"), "contract")
    assumptions_data = contract_data.get("assumptions", [])
    if not isinstance(assumptions_data, list):
        raise ValueError("contract.assumptions must be a list")
    assumptions: list[Assumption] = []
    for index, value in enumerate(assumptions_data):
        item = _object(value, f"contract.assumptions[{index}]")
        if set(item) != {"id", "statement"}:
            raise ValueError(f"contract.assumptions[{index}] has unexpected fields")
        assumptions.append(
            Assumption(
                assumption_id=_string(item.get("id"), "assumption.id"),
                statement=_string(item.get("statement"), "assumption.statement"),
            )
        )
    contract = IntentContract(
        contract_id=_string(contract_data.get("contract_id"), "contract.contract_id"),
        version=_integer(contract_data.get("version"), "contract.version"),
        goal=_string(contract_data.get("goal"), "contract.goal"),
        constraints=_strings(contract_data.get("constraints"), "contract.constraints"),
        permitted_actions=_strings(
            contract_data.get("permitted_actions"), "contract.permitted_actions"
        ),
        prohibited_actions=_strings(
            contract_data.get("prohibited_actions"), "contract.prohibited_actions"
        ),
        assumptions=tuple(assumptions),
        acceptance_criteria=_strings(
            contract_data.get("acceptance_criteria"), "contract.acceptance_criteria"
        ),
    )
    raw_cases = document.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("dataset.cases must be a non-empty list")

    cases: list[SemanticEvaluationCase] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(raw_cases):
        item = _object(value, f"cases[{index}]")
        case_id = _string(item.get("case_id"), f"cases[{index}].case_id")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)
        expected_drift = item.get("expected_drift")
        if not isinstance(expected_drift, bool):
            raise ValueError(f"cases[{index}].expected_drift must be a boolean")
        raw_plan = item.get("plan")
        if not isinstance(raw_plan, list) or not raw_plan:
            raise ValueError(f"cases[{index}].plan must be a non-empty list")
        plan: list[PlanStep] = []
        for step_index, step_value in enumerate(raw_plan):
            step = _object(step_value, f"cases[{index}].plan[{step_index}]")
            expected_keys = {
                "step_id",
                "description",
                "action_category",
                "acceptance_criteria",
                "dependencies",
            }
            if set(step) != expected_keys:
                raise ValueError(f"cases[{index}].plan[{step_index}] has unexpected fields")
            plan.append(
                PlanStep(
                    step_id=_string(step.get("step_id"), "step.step_id"),
                    description=_string(step.get("description"), "step.description"),
                    action_category=_string(step.get("action_category"), "step.action_category"),
                    acceptance_criteria=_strings(
                        step.get("acceptance_criteria"), "step.acceptance_criteria"
                    ),
                    dependencies=_strings(step.get("dependencies"), "step.dependencies"),
                )
            )
        cases.append(
            SemanticEvaluationCase(
                case_id=case_id,
                request=SemanticComparisonRequest(contract=contract, plan=tuple(plan)),
                expected_drift=expected_drift,
            )
        )
    return labeling_policy, tuple(cases)


def calculate_semantic_metrics(
    cases: Sequence[SemanticEvaluationCase],
    results: Sequence[SemanticDriftResult],
) -> SemanticEvaluationMetrics:
    """Calculate metrics without invoking a model, so formulas can be tested offline."""
    if len(cases) != len(results):
        raise ValueError("cases and results must have the same length")
    if not cases:
        raise ValueError("at least one evaluation case is required")

    true_positives = false_positives = true_negatives = false_negatives = 0
    status_counts = {status.value: 0 for status in SemanticStatus}
    for case, result in zip(cases, results, strict=True):
        predicted_drift = result.review_recommended
        if case.expected_drift and predicted_drift:
            true_positives += 1
        elif case.expected_drift:
            false_negatives += 1
        elif predicted_drift:
            false_positives += 1
        else:
            true_negatives += 1
        status_counts[result.status.value] += 1

    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    negative_denominator = false_positives + true_negatives
    precision = (
        true_positives / precision_denominator if precision_denominator else None
    )
    recall = true_positives / recall_denominator if recall_denominator else None
    false_pause_rate = (
        false_positives / negative_denominator if negative_denominator else None
    )
    missed_drift_rate = (
        false_negatives / recall_denominator if recall_denominator else None
    )

    latencies = sorted(max(0.0, result.latency_ms) for result in results)
    p95_index = max(0, ceil(0.95 * len(latencies)) - 1)
    prompt_tokens_total = sum(
        result.prompt_tokens for result in results if result.prompt_tokens is not None
    )
    completion_tokens_total = sum(
        result.completion_tokens
        for result in results
        if result.completion_tokens is not None
    )
    token_usage_cases = sum(result.total_tokens is not None for result in results)
    measured_total_tokens = sum(
        result.total_tokens for result in results if result.total_tokens is not None
    )
    average_tokens = (
        measured_total_tokens / token_usage_cases if token_usage_cases else None
    )

    return SemanticEvaluationMetrics(
        case_count=len(cases),
        true_positives=true_positives,
        false_positives=false_positives,
        true_negatives=true_negatives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        false_pause_rate=false_pause_rate,
        missed_drift_rate=missed_drift_rate,
        mean_latency_ms=fmean(latencies),
        p95_latency_ms=latencies[p95_index],
        prompt_tokens_total=prompt_tokens_total,
        completion_tokens_total=completion_tokens_total,
        token_usage_cases=token_usage_cases,
        average_total_tokens_per_measured_case=average_tokens,
        status_counts=status_counts,
    )


def evaluate_semantic_drift(
    cases: Sequence[SemanticEvaluationCase], provider: SemanticDriftProvider
) -> tuple[SemanticEvaluationMetrics, tuple[SemanticDriftResult, ...]]:
    """Run each labelled case once, then return metrics and individual validated results."""
    results = tuple(analyze_semantic_drift(case.request, provider) for case in cases)
    return calculate_semantic_metrics(cases, results), results



def evaluate_semantic_drift_trials(
    cases: Sequence[SemanticEvaluationCase],
    provider: SemanticDriftProvider,
    *,
    trials: int = 1,
) -> tuple[
    SemanticEvaluationMetrics,
    tuple[SemanticEvaluationMetrics, ...],
    tuple[tuple[SemanticDriftResult, ...], ...],
]:
    """Run a bounded number of sequential trials and return per-trial and aggregate metrics."""
    if type(trials) is not int or not 1 <= trials <= 100:
        raise ValueError("trials must be an integer between 1 and 100")
    if not cases:
        raise ValueError("at least one evaluation case is required")

    trial_results: list[tuple[SemanticDriftResult, ...]] = []
    trial_metrics: list[SemanticEvaluationMetrics] = []
    for _ in range(trials):
        results = tuple(analyze_semantic_drift(case.request, provider) for case in cases)
        trial_results.append(results)
        trial_metrics.append(calculate_semantic_metrics(cases, results))

    aggregate_cases = tuple(cases) * trials
    aggregate_results = tuple(result for results in trial_results for result in results)
    aggregate_metrics = calculate_semantic_metrics(aggregate_cases, aggregate_results)
    return aggregate_metrics, tuple(trial_metrics), tuple(trial_results)

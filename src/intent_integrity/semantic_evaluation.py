"""Small, reproducible evaluation harness for advisory semantic drift detection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from statistics import fmean

from intent_integrity.semantic import (
    SemanticDriftProvider,
    SemanticDriftResult,
    SemanticStatus,
    SemanticComparisonRequest,
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

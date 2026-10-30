"""Run the labelled semantic drift benchmark against an optional local Gemma model.

Example:
    python examples/evaluate_semantic_drift.py --model gemma3:4b
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from intent_integrity.semantic import GemmaOllamaProvider, SemanticStatus
from intent_integrity.semantic_evaluation import (
    evaluate_semantic_drift_trials,
    load_semantic_evaluation_cases,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "benchmarks" / "semantic_drift_cases.json",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--trials", type=int, default=1, help="Sequential trials per case (1–100).")
    args = parser.parse_args()
    if not 1 <= args.trials <= 100:
        parser.error("--trials must be between 1 and 100")

    labeling_policy, cases = load_semantic_evaluation_cases(args.dataset)
    provider = GemmaOllamaProvider(
        base_url=args.base_url, model=args.model, timeout_seconds=args.timeout
    )
    metrics, trial_metrics, results_by_trial = evaluate_semantic_drift_trials(
        cases, provider, trials=args.trials
    )
    report = {
        "dataset": str(args.dataset),
        "labeling_policy": labeling_policy,
        "provider": {
            "type": "ollama-compatible",
            "base_url": args.base_url,
            "model": args.model,
            "timeout_seconds": args.timeout,
        },
        "trial_count": args.trials,
        "metrics": metrics.to_dict(),
        "per_trial_metrics": [item.to_dict() for item in trial_metrics],
        "cases": [
            {
                "trial": trial_index,
                "case_id": case.case_id,
                "expected_drift": case.expected_drift,
                "predicted_drift": result.review_recommended,
                "result": result.to_dict(),
            }
            for trial_index, trial_results in enumerate(results_by_trial, start=1)
            for case, result in zip(cases, trial_results, strict=True)
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return (
        2
        if any(
            result.status == SemanticStatus.UNAVAILABLE
            for trial_results in results_by_trial
            for result in trial_results
        )
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())

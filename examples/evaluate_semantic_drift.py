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
    evaluate_semantic_drift,
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
    args = parser.parse_args()

    labeling_policy, cases = load_semantic_evaluation_cases(args.dataset)
    provider = GemmaOllamaProvider(
        base_url=args.base_url, model=args.model, timeout_seconds=args.timeout
    )
    metrics, results = evaluate_semantic_drift(cases, provider)
    report = {
        "dataset": str(args.dataset),
        "labeling_policy": labeling_policy,
        "provider": {"type": "ollama-compatible", "model": args.model},
        "metrics": metrics.to_dict(),
        "cases": [
            {
                "case_id": case.case_id,
                "expected_drift": case.expected_drift,
                "predicted_drift": result.review_recommended,
                "result": result.to_dict(),
            }
            for case, result in zip(cases, results, strict=True)
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 2 if any(result.status == SemanticStatus.UNAVAILABLE for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

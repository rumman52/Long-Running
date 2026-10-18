"""Run the labelled semantic drift benchmark against an optional local Gemma model.

Example:
    python examples/evaluate_semantic_drift.py --model gemma3:4b
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from intent_integrity import Assumption, IntentContract, PlanStep
from intent_integrity.semantic import (
    GemmaOllamaProvider,
    SemanticComparisonRequest,
    SemanticStatus,
)
from intent_integrity.semantic_evaluation import SemanticEvaluationCase, evaluate_semantic_drift


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


def load_cases(path: Path) -> tuple[str, tuple[SemanticEvaluationCase, ...]]:
    """Load and validate the benchmark JSON without trusting arbitrary object shapes."""
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

    labeling_policy, cases = load_cases(args.dataset)
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

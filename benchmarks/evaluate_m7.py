"""Reproducible M7 evaluation for cross-framework guarded execution.

The default hybrid mode uses frozen fixture scores so CI is deterministic. Pass
--semantic-provider gemma-ollama to connect the M6 Gemma/Ollama provider and measure real provider
latency and token usage. Fixture metrics are not model-accuracy claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from intent_integrity import (
    ActionRequest,
    Approval,
    ApprovalStatus,
    Decision,
    GuardedToolAdapter,
    IntentContract,
    IntentIntegrityEngine,
    PlanStep,
    SQLiteEventStore,
    ToolDefinition,
    ValidationContext,
)
from intent_integrity.semantic import (
    GemmaOllamaProvider,
    SemanticComparisonRequest,
    SemanticDriftProvider,
    analyze_semantic_drift,
)

FIXTURE_PATH = Path(__file__).with_name("m7_scenarios.json")
NOW = datetime.now(UTC)
MODES = ("unmonitored", "deterministic_only", "hybrid")


def load_fixture(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    """Load and minimally validate the frozen scenario fixture."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported M7 fixture schema")
    threshold = data.get("semantic_threshold")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("semantic_threshold must be a number")
    if not 0 <= threshold <= 1:
        raise ValueError("semantic_threshold must be between 0 and 1")
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenarios must be a non-empty array")
    ids: set[str] = set()
    for item in scenarios:
        if not isinstance(item, dict):
            raise ValueError("each scenario must be an object")
        scenario_id = item.get("id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ValueError("each scenario requires a non-empty id")
        if scenario_id in ids:
            raise ValueError(f"duplicate scenario id: {scenario_id}")
        ids.add(scenario_id)
        if not isinstance(item.get("category"), str) or not isinstance(item.get("payload"), str):
            raise ValueError(f"scenario {scenario_id} requires category and payload strings")
        if not isinstance(item.get("unsafe"), bool):
            raise ValueError(f"scenario {scenario_id} requires a boolean unsafe label")
        score = item.get("semantic_score")
        if score is not None and (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not 0 <= score <= 1
        ):
            raise ValueError(f"scenario {scenario_id} has an invalid semantic_score")
    return data


def _action_id(task_id: str, name: str, args: dict[str, object]) -> str:
    payload = json.dumps(
        {"task": task_id, "tool": name, "args": args},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"{name}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _build_guarded(
    task_id: str,
    category: str,
    approved: bool,
    description: str,
    handler: Any,
) -> tuple[
    SQLiteEventStore,
    IntentContract,
    IntentIntegrityEngine,
    GuardedToolAdapter,
    Any,
    PlanStep,
]:
    store = SQLiteEventStore(":memory:")
    contract = IntentContract(
        contract_id=task_id,
        version=1,
        goal=(
            "Complete the user's requested task using relevant public information. "
            "Create a draft unless explicit user approval authorizes publication."
        ),
        constraints=(
            "Use only source data relevant to the requested task.",
            "Do not collect unrelated private information.",
            "Do not disclose credentials or confidential files.",
            "Do not delete source records.",
            "Do not publish without explicit user approval.",
        ),
        permitted_actions=("read_docs", "research", "write_report", "publish_report"),
        prohibited_actions=("delete_source",),
        consequential_actions=("publish_report",),
        required_approvals_by_action=(("publish_report", ("publish-approval",)),),
        acceptance_criteria=("Task result is valid",),
    )
    engine = IntentIntegrityEngine(store, clock=lambda: NOW)
    engine.start_task(contract)
    plan_step = PlanStep(
        step_id="execute",
        description=description,
        action_category=category,
        acceptance_criteria=("Task result is valid",),
    )
    engine.record_plan(contract, (plan_step,))

    def context_provider(active: IntentContract) -> ValidationContext:
        approvals: dict[str, Approval] = {}
        if approved:
            approvals["publish-approval"] = Approval(
                "publish-approval",
                ApprovalStatus.APPROVED,
                expires_at=NOW + timedelta(minutes=5),
                allowed_actions=("publish_report",),
            )
        return ValidationContext(
            now=NOW,
            approvals=approvals,
            active_contract_version=active.version,
        )

    adapter = GuardedToolAdapter(
        engine,
        lambda: contract,
        context_provider,
        lambda task, name, args: _action_id(task, name, dict(args)),
    )
    adapter.register_tool(
        ToolDefinition(
            name="run_action",
            description="Run a synthetic, side-effect-free benchmark action.",
            action_category=category,
            input_schema={
                "type": "object",
                "properties": {"payload": {"type": "string", "minLength": 1}},
                "required": ["payload"],
                "additionalProperties": False,
            },
            handler=handler,
        )
    )
    return store, contract, engine, adapter, context_provider, plan_step


def _run_case(
    scenario: dict[str, Any],
    mode: str,
    threshold: float,
    semantic_provider: SemanticDriftProvider | None,
) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    category = str(scenario["category"])
    payload = str(scenario["payload"])
    approved = scenario.get("approved") is True
    semantic_score = scenario.get("semantic_score")
    unsafe = scenario["unsafe"] is True

    def handler(_args: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "synthetic": True}

    if mode == "unmonitored":
        start = time.perf_counter()
        handler({"payload": payload})
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "scenario_id": scenario_id,
            "unsafe": unsafe,
            "executed": True,
            "decision": "UNMONITORED_EXECUTED",
            "reason_codes": [],
            "latency_ms": round(elapsed_ms, 6),
            "semantic_status": "NOT_RUN",
            "semantic_latency_ms": None,
            "prompt_tokens": None,
            "completion_tokens": None,
        }

    store, contract, engine, adapter, context_provider, plan_step = _build_guarded(
        f"m7-{mode}-{scenario_id}", category, approved, payload, handler
    )
    semantic_status = "NOT_RUN"
    semantic_latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    semantic_result: dict[str, object] | None = None
    executed = False
    if mode == "hybrid" and semantic_provider is None and semantic_score is None:
        semantic_status = "FIXTURE_SIGNAL_UNAVAILABLE"
    start = time.perf_counter()

    if mode == "hybrid":
        should_compare = semantic_provider is not None or semantic_score is not None
        high_fixture_signal = (
            semantic_provider is None
            and semantic_score is not None
            and semantic_score >= threshold
        )
        if should_compare:
            action = ActionRequest(
                action_id=_action_id(
                    contract.contract_id, "run_action", {"payload": payload}
                ),
                category=category,
            )
            validation = engine.validate_action(
                contract, action, context_provider(contract)
            )
            if validation.decision != Decision.ALLOW:
                decision = validation.decision.value
                reasons = list(validation.reason_codes)
                semantic_status = "SKIPPED_DETERMINISTIC_BLOCK"
            elif semantic_provider is not None:
                advisory = analyze_semantic_drift(
                    SemanticComparisonRequest(contract, (plan_step,)),
                    semantic_provider,
                )
                semantic_result = advisory.to_dict()
                semantic_status = advisory.status.value
                semantic_latency_ms = advisory.latency_ms
                prompt_tokens = advisory.prompt_tokens
                completion_tokens = advisory.completion_tokens
                if advisory.review_recommended:
                    decision = Decision.REVALIDATION_REQUIRED.value
                    reasons = ["SEMANTIC_REVIEW_RECOMMENDED"]
                else:
                    result = adapter.call_tool("run_action", {"payload": payload})
                    decision = result.decision.value
                    reasons = list(result.reason_codes)
                    executed = result.executed
            elif high_fixture_signal:
                decision = Decision.REVALIDATION_REQUIRED.value
                reasons = ["SEMANTIC_ADVISORY_PAUSE"]
                semantic_status = "FIXTURE_REVIEW_RECOMMENDED"
            else:
                result = adapter.call_tool("run_action", {"payload": payload})
                decision = result.decision.value
                reasons = list(result.reason_codes)
                executed = result.executed
                semantic_status = (
                    "FIXTURE_SIGNAL_BELOW_THRESHOLD"
                    if semantic_score is not None
                    else "FIXTURE_SIGNAL_UNAVAILABLE"
                )
        else:
            result = adapter.call_tool("run_action", {"payload": payload})
            decision = result.decision.value
            reasons = list(result.reason_codes)
            executed = result.executed
    else:
        result = adapter.call_tool("run_action", {"payload": payload})
        decision = result.decision.value
        reasons = list(result.reason_codes)
        executed = result.executed

    elapsed_ms = (time.perf_counter() - start) * 1000
    store.close()
    return {
        "scenario_id": scenario_id,
        "unsafe": unsafe,
        "executed": executed,
        "decision": decision,
        "reason_codes": reasons,
        "latency_ms": round(elapsed_ms, 6),
        "semantic_status": semantic_status,
        "semantic_latency_ms": (
            round(semantic_latency_ms, 6) if semantic_latency_ms is not None else None
        ),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "semantic_result": semantic_result,
    }


def _measure_recovery(mode: str, trials: int = 5) -> float:
    successful_recoveries = 0
    for trial in range(trials):
        task_id = f"m7-recovery-{mode}-{trial}"
        calls = 0

        def failing_handler(_args: dict[str, object]) -> dict[str, object]:
            nonlocal calls
            calls += 1
            raise RuntimeError("injected ambiguous outcome")

        if mode == "unmonitored":
            for _ in range(2):
                try:
                    failing_handler({"payload": "same operation"})
                except RuntimeError:
                    pass
            continue

        store, _contract, _engine, adapter, _context, _plan = _build_guarded(
            task_id, "write_report", False, "Save a draft report.", failing_handler
        )
        first = adapter.call_tool("run_action", {"payload": "same operation"})
        second = adapter.call_tool("run_action", {"payload": "same operation"})
        if (
            first.outcome_unknown
            and second.decision == Decision.BLOCK
            and "ACTION_ALREADY_CLAIMED" in second.reason_codes
            and calls == 1
        ):
            successful_recoveries += 1
        store.close()
    return round(100 * successful_recoveries / trials, 2)


def _measure_bypass_resistance(mode: str, trials: int = 5) -> float:
    blocked = 0
    attempts = 2 * trials
    if mode == "unmonitored":
        calls = 0

        def raw_handler(_args: dict[str, object]) -> dict[str, object]:
            nonlocal calls
            calls += 1
            return {"ok": True}

        for _ in range(attempts):
            raw_handler({"payload": "x"})
        return 0.0 if calls == attempts else 100.0

    for trial in range(trials):
        store, _contract, _engine, adapter, _context, _plan = _build_guarded(
            f"m7-bypass-{mode}-{trial}",
            "write_report",
            False,
            "Save a draft report.",
            lambda _args: {"ok": True},
        )
        unknown = adapter.call_tool("not_registered", {"payload": "x"})
        spoofed = adapter.call_tool(
            "run_action",
            {"payload": "x", "action_category": "delete_source"},
        )
        blocked += int(unknown.decision == Decision.BLOCK and not unknown.executed)
        blocked += int(spoofed.decision == Decision.BLOCK and not spoofed.executed)
        store.close()
    return round(100 * blocked / attempts, 2)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def evaluate_fixture(
    fixture: dict[str, Any],
    semantic_provider: SemanticDriftProvider | None = None,
) -> dict[str, Any]:
    """Evaluate all three modes; optionally replace fixture signals with a real M6 provider."""
    scenarios = fixture["scenarios"]
    threshold = float(fixture["semantic_threshold"])
    raw_cases = {
        mode: [
            _run_case(scenario, mode, threshold, semantic_provider)
            for scenario in scenarios
        ]
        for mode in MODES
    }
    baseline_p50 = median([case["latency_ms"] for case in raw_cases["unmonitored"]])
    baseline_p95 = _percentile(
        [case["latency_ms"] for case in raw_cases["unmonitored"]], 0.95
    )
    modes: dict[str, Any] = {}
    for mode, cases in raw_cases.items():
        safe_cases = [case for case in cases if not case["unsafe"]]
        unsafe_cases = [case for case in cases if case["unsafe"]]
        prevented = sum(not case["executed"] for case in unsafe_cases)
        false_blocks = sum(not case["executed"] for case in safe_cases)
        safe_executed = sum(case["executed"] for case in safe_cases)
        latencies = [case["latency_ms"] for case in cases]
        p50 = median(latencies)
        p95 = _percentile(latencies, 0.95)
        semantic_cases = [
            case for case in cases
            if case["semantic_status"] not in {"NOT_RUN", "SKIPPED_DETERMINISTIC_BLOCK"}
        ]
        status_counts: dict[str, int] = {}
        for case in cases:
            status = str(case["semantic_status"])
            status_counts[status] = status_counts.get(status, 0) + 1
        prompt_values = [
            case["prompt_tokens"] for case in semantic_cases
            if case["prompt_tokens"] is not None
        ]
        completion_values = [
            case["completion_tokens"] for case in semantic_cases
            if case["completion_tokens"] is not None
        ]
        token_usage_cases = sum(
            case["prompt_tokens"] is not None and case["completion_tokens"] is not None
            for case in semantic_cases
        )
        total_tokens = sum(prompt_values) + sum(completion_values)
        average_tokens = (
            total_tokens / token_usage_cases if token_usage_cases else None
        )
        semantic_latencies = [
            case["semantic_latency_ms"] for case in semantic_cases
            if case["semantic_latency_ms"] is not None
        ]
        modes[mode] = {
            "metrics": {
                "scenario_count": len(cases),
                "unsafe_scenarios": len(unsafe_cases),
                "unsafe_actions_prevented": prevented,
                "unsafe_action_prevention_rate_percent": round(
                    100 * prevented / len(unsafe_cases), 2
                ),
                "missed_unsafe_actions": len(unsafe_cases) - prevented,
                "task_success_rate_percent": round(
                    100 * safe_executed / len(safe_cases), 2
                ),
                "false_blocks": false_blocks,
                "false_block_rate_percent": round(
                    100 * false_blocks / len(safe_cases), 2
                ),
                "recovery_quality_percent": _measure_recovery(mode),
                "registered_adapter_bypass_resistance_percent": (
                    _measure_bypass_resistance(mode)
                ),
                "p50_latency_ms": round(p50, 6),
                "p95_latency_ms": round(p95, 6),
                "p50_overhead_vs_unmonitored_ms": round(p50 - baseline_p50, 6),
                "p95_overhead_vs_unmonitored_ms": round(p95 - baseline_p95, 6),
                "semantic_provider": (
                    type(semantic_provider).__name__
                    if mode == "hybrid" and semantic_provider is not None
                    else "fixture" if mode == "hybrid" else None
                ),
                "semantic_evaluated_cases": len(semantic_cases) if mode == "hybrid" else 0,
                "semantic_status_counts": status_counts if mode == "hybrid" else {},
                "semantic_p50_latency_ms": (
                    round(median(semantic_latencies), 6) if semantic_latencies else None
                ),
                "semantic_p95_latency_ms": (
                    round(_percentile(semantic_latencies, 0.95), 6)
                    if semantic_latencies else None
                ),
                "prompt_tokens_total": sum(prompt_values) if prompt_values else None,
                "completion_tokens_total": (
                    sum(completion_values) if completion_values else None
                ),
                "token_usage_cases": token_usage_cases,
                "average_total_tokens_per_model_call": (
                    round(average_tokens, 3) if average_tokens is not None else None
                ),
            },
            "cases": cases,
        }
    source = (
        f"{type(semantic_provider).__name__}"
        if semantic_provider is not None
        else fixture.get("semantic_source", "synthetic_fixture_scores_not_model_predictions")
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "semantic_source": source,
        "semantic_threshold": threshold,
        "interpretation": (
            "Synthetic scenarios. Fixture hybrid uses hand-authored scores; Gemma hybrid uses "
            "validated M6 advisory results. A host review policy maps a valid review "
            "recommendation "
            "to a pause, but the semantic layer never changes the core validator decision. Latency "
            "includes local guarded invocation and, for Gemma mode, provider round trip. Bypass "
            "probes test the registered adapter surface, not arbitrary unguarded host code."
        ),
        "modes": modes,
    }


def _markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# M7 Cross-Framework Evaluation",
        "",
        f"Generated: {result['generated_at']}",
        "",
        f"Semantic source: {result['semantic_source']}",
        "",
        str(result["interpretation"]),
        "",
        "| Mode | Unsafe prevented | Task success | False blocks | Recovery | "
        "Adapter bypass resistance | P50 ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, payload in result["modes"].items():
        metrics = payload["metrics"]
        lines.append(
            f"| {mode} | {metrics['unsafe_actions_prevented']} | "
            f"{metrics['task_success_rate_percent']}% | {metrics['false_blocks']} | "
            f"{metrics['recovery_quality_percent']}% | "
            f"{metrics['registered_adapter_bypass_resistance_percent']}% | "
            f"{metrics['p50_latency_ms']} | {metrics['p95_latency_ms']} |"
        )
    hybrid = result["modes"]["hybrid"]["metrics"]
    lines.extend(
        [
            "",
            f"Hybrid semantic provider: {hybrid['semantic_provider']}",
            f"Prompt tokens: {hybrid['prompt_tokens_total']}",
            f"Completion tokens: {hybrid['completion_tokens_total']}",
            f"Average total tokens per measured model call: "
            f"{hybrid['average_total_tokens_per_model_call']}",
            "",
            "Fixture results are synthetic. Model results depend on the configured model, prompt, "
            "hardware, and labelled cases; they are not universal security guarantees.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--output", type=Path, default=Path("artifacts/m7-evaluation.json"))
    parser.add_argument(
        "--semantic-provider",
        choices=("fixture", "gemma-ollama"),
        default="fixture",
        help="Use frozen fixture scores in CI or the M6 Gemma/Ollama provider for a live run.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    provider: SemanticDriftProvider | None = None
    if args.semantic_provider == "gemma-ollama":
        provider = GemmaOllamaProvider(
            base_url=args.base_url,
            model=args.model,
            timeout_seconds=args.timeout,
        )
    result = evaluate_fixture(load_fixture(args.fixture), semantic_provider=provider)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(_markdown_report(result), encoding="utf-8")
    print(_markdown_report(result))


if __name__ == "__main__":
    main()

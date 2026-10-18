"""Run a local MCP stdio demo with guarded fake report tools; no external side effects."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from intent_integrity import (
    GuardedToolAdapter, IntentContract, IntentIntegrityEngine, MCPStdioServer, PlanStep,
    SQLiteEventStore, ToolDefinition, ValidationContext,
)


def main() -> None:
    contract = IntentContract(
        contract_id="mcp-demo-report",
        version=1,
        goal="Draft an accurate report; do not publish without approval.",
        permitted_actions=("write_report", "publish_report"),
        prohibited_actions=("delete_source",),
        consequential_actions=("publish_report",),
        required_approvals_by_action=(("publish_report", ("publish-approval",)),),
        acceptance_criteria=("Report is accurate", "User approves final report"),
    )
    plan = (
        PlanStep("draft", "Write a report draft", "write_report",
                 acceptance_criteria=("Report is accurate",)),
        PlanStep("publish", "Publish only after approval", "publish_report",
                 acceptance_criteria=("User approves final report",), dependencies=("draft",)),
    )
    with TemporaryDirectory(prefix="intent-integrity-mcp-") as temp:
        with SQLiteEventStore(Path(temp) / "ledger.sqlite3") as store:
            engine = IntentIntegrityEngine(store)
            engine.start_task(contract)
            drift = engine.record_plan(contract, plan)
            if drift.has_blocking_drift:
                raise RuntimeError(f"Invalid demo plan: {drift.to_dict()}")

            def context_provider(active: IntentContract) -> ValidationContext:
                return ValidationContext(
                    now=datetime.now(UTC), evidence={}, approvals={},
                    active_contract_version=active.version,
                )

            def action_id(task_id: str, name: str, args: object) -> str:
                payload = json.dumps(
                    {"task": task_id, "tool": name, "args": args},
                    sort_keys=True, separators=(",", ":"), allow_nan=False,
                )
                return f"{name}:{hashlib.sha256(payload.encode()).hexdigest()}"

            adapter = GuardedToolAdapter(
                engine, lambda: contract, context_provider, action_id,
            )
            adapter.register_tool(ToolDefinition(
                name="save_draft",
                description="Save a local demonstration report draft.",
                action_category="write_report",
                input_schema={
                    "type": "object",
                    "properties": {"report": {"type": "string", "minLength": 1}},
                    "required": ["report"],
                    "additionalProperties": False,
                },
                handler=lambda args: {"saved": True, "characters": len(str(args["report"]))},
            ))
            adapter.register_tool(ToolDefinition(
                name="publish_report",
                description="Demo-only publishing action; approval is required.",
                action_category="publish_report",
                input_schema={
                    "type": "object", "properties": {"report": {"type": "string"}},
                    "required": ["report"], "additionalProperties": False,
                },
                handler=lambda _args: {"published": True, "demo_only": True},
            ))
            MCPStdioServer(adapter).serve_stdio(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()

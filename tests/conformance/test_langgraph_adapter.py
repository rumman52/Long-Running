from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from intent_integrity import (
    Decision,
    GuardedToolAdapter,
    IntentContract,
    IntentIntegrityEngine,
    PlanStep,
    SQLiteEventStore,
    ToolDefinition,
    ValidationContext,
)
from intent_integrity.integrations.langgraph import build_langgraph_tools

pytest.importorskip("langgraph")

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def setup_tools():
    store = SQLiteEventStore(":memory:")
    contract = IntentContract(
        contract_id="langgraph-consumer-test",
        version=1,
        goal="Save a report draft for review.",
        permitted_actions=("write_report",),
        acceptance_criteria=("Draft saved",),
    )
    engine = IntentIntegrityEngine(store, clock=lambda: NOW)
    engine.start_task(contract)
    engine.record_plan(
        contract,
        (
            PlanStep(
                "draft",
                "Save report draft",
                "write_report",
                acceptance_criteria=("Draft saved",),
            ),
        ),
    )

    def context_provider(active: IntentContract) -> ValidationContext:
        return ValidationContext(now=NOW, active_contract_version=active.version)

    def action_id(task_id: str, name: str, args) -> str:
        raw = json.dumps(
            {"task": task_id, "name": name, "args": args},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return f"{name}:{hashlib.sha256(raw.encode()).hexdigest()}"

    adapter = GuardedToolAdapter(engine, lambda: contract, context_provider, action_id)
    calls: list[dict[str, object]] = []
    definition = ToolDefinition(
        name="save_report",
        description="Save a local report draft.",
        action_category="write_report",
        input_schema={
            "type": "object",
            "properties": {"report": {"type": "string", "minLength": 1}},
            "required": ["report"],
            "additionalProperties": False,
        },
        handler=lambda args: (calls.append(dict(args)) or {"saved": True}),
    )
    tools = build_langgraph_tools(adapter, [definition])
    return store, tools, calls


def _invoke_tool_node(tool_node: object, tool_name: str, args: dict[str, object], call_id: str):
    from langchain_core.messages import AIMessage

    message = AIMessage(
        content="",
        tool_calls=[
            {"name": tool_name, "args": args, "id": call_id, "type": "tool_call"}
        ],
    )
    return tool_node.invoke({"messages": [message]})


def test_langgraph_tool_node_uses_guard_and_blocks_duplicate_action() -> None:
    from langgraph.prebuilt import ToolNode

    store, tools, calls = setup_tools()
    try:
        node = ToolNode(tools)
        first = _invoke_tool_node(node, "save_report", {"report": "Quarterly"}, "call-1")
        first_result = json.loads(first["messages"][-1].content)
        second = _invoke_tool_node(node, "save_report", {"report": "Quarterly"}, "call-2")
        second_result = json.loads(second["messages"][-1].content)

        assert first_result["decision"] == Decision.ALLOW.value
        assert first_result["executed"] is True
        assert second_result["decision"] == Decision.BLOCK.value
        assert "ACTION_ALREADY_CLAIMED" in second_result["reason_codes"]
        assert len(calls) == 1
    finally:
        store.close()


def test_langgraph_schema_rejects_attempt_to_override_registered_category() -> None:
    store, tools, calls = setup_tools()
    try:
        with pytest.raises(ValueError):
            tools[0].invoke(
                {"report": "Quarterly", "action_category": "delete_source"}
            )
        assert calls == []
    finally:
        store.close()

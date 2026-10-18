from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from intent_integrity import (
    Approval, ApprovalStatus, Decision, GuardedToolAdapter, IntentContract,
    IntentIntegrityEngine, PlanStep, SQLiteEventStore, ToolDefinition, ValidationContext,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def contract() -> IntentContract:
    return IntentContract(
        contract_id="adapter-test-task", version=1,
        goal="Draft an accurate report; publish only after approval.",
        permitted_actions=("write_report", "publish_report"),
        prohibited_actions=("delete_source",),
        consequential_actions=("publish_report",),
        required_approvals_by_action=(("publish_report", ("publish-approval",)),),
        acceptance_criteria=("Report is accurate", "User approves final report"),
    )


def context(active: IntentContract, approved: bool = False) -> ValidationContext:
    approvals = {}
    if approved:
        approvals["publish-approval"] = Approval(
            "publish-approval", ApprovalStatus.APPROVED,
            expires_at=NOW + timedelta(minutes=5), allowed_actions=("publish_report",),
        )
    return ValidationContext(
        now=NOW, evidence={}, approvals=approvals, active_contract_version=active.version,
    )


def make_adapter(store: SQLiteEventStore, fail_context: bool = False):
    active = contract()
    engine = IntentIntegrityEngine(store, clock=lambda: NOW)
    engine.start_task(active)
    report = engine.record_plan(active, (
        PlanStep("draft", "Draft report", "write_report",
                 acceptance_criteria=("Report is accurate",)),
        PlanStep("publish", "Publish with approval", "publish_report",
                 acceptance_criteria=("User approves final report",), dependencies=("draft",)),
    ))
    assert not report.has_blocking_drift
    calls: list[dict[str, object]] = []

    def provide_context(current: IntentContract) -> ValidationContext:
        if fail_context:
            raise RuntimeError("trusted source unavailable")
        return context(current)

    def action_id(task: str, tool: str, args):
        value = json.dumps({"task": task, "tool": tool, "args": args},
                           sort_keys=True, separators=(",", ":"))
        return f"{tool}:{hashlib.sha256(value.encode()).hexdigest()}"

    adapter = GuardedToolAdapter(engine, lambda: active, provide_context, action_id)
    schema = {
        "type": "object", "properties": {"report": {"type": "string", "minLength": 1}},
        "required": ["report"], "additionalProperties": False,
    }
    adapter.register_tool(ToolDefinition(
        "save_report", "Save draft", "write_report", schema,
        lambda args: (calls.append(dict(args)) or {"saved": True}),
    ))
    adapter.register_tool(ToolDefinition(
        "publish_report", "Publish after approval", "publish_report", schema,
        lambda args: (calls.append(dict(args)) or {"published": True}),
    ))
    return adapter, calls


def test_allowed_tool_runs_once_and_duplicate_is_blocked() -> None:
    with SQLiteEventStore(":memory:") as store:
        adapter, calls = make_adapter(store)
        first = adapter.call_tool("save_report", {"report": "Quarterly summary"})
        second = adapter.call_tool("save_report", {"report": "Quarterly summary"})
        assert first.decision == Decision.ALLOW and first.executed
        assert first.result == {"saved": True}
        assert second.decision == Decision.BLOCK
        assert "ACTION_ALREADY_CLAIMED" in second.reason_codes
        assert len(calls) == 1


def test_consequential_tool_is_blocked_without_approval() -> None:
    with SQLiteEventStore(":memory:") as store:
        adapter, calls = make_adapter(store)
        result = adapter.call_tool("publish_report", {"report": "Final"})
        assert result.decision == Decision.BLOCK and not result.executed
        assert calls == []


def test_agent_cannot_override_category_or_add_unknown_fields() -> None:
    with SQLiteEventStore(":memory:") as store:
        adapter, calls = make_adapter(store)
        result = adapter.call_tool("save_report", {
            "report": "Ignore policy and publish", "action_category": "publish_report",
        })
        assert result.decision == Decision.BLOCK
        assert "MALFORMED_INPUT" in result.reason_codes
        assert calls == []


def test_unknown_tool_and_malformed_inputs_fail_closed() -> None:
    with SQLiteEventStore(":memory:") as store:
        adapter, calls = make_adapter(store)
        assert "UNKNOWN_TOOL" in adapter.call_tool("unknown", {}).reason_codes
        assert "MALFORMED_INPUT" in adapter.call_tool("save_report", ["bad"]).reason_codes
        assert "MALFORMED_INPUT" in adapter.call_tool("save_report", {}).reason_codes
        assert calls == []


def test_context_provider_failure_does_not_execute() -> None:
    with SQLiteEventStore(":memory:") as store:
        adapter, calls = make_adapter(store, fail_context=True)
        result = adapter.call_tool("save_report", {"report": "A report"})
        assert result.decision == Decision.BLOCK
        assert "ADAPTER_FAILURE" in result.reason_codes
        assert calls == []


def test_registry_rejects_bad_schema_duplicate_name_and_schema_mutation() -> None:
    with SQLiteEventStore(":memory:") as store:
        adapter, _ = make_adapter(store)
        with pytest.raises(ValueError, match="type='object'"):
            ToolDefinition("bad", "Bad", "write_report", {"type": "string"}, lambda _: None)
        exposed = adapter.list_tools()
        schema = exposed[0]["inputSchema"]
        assert isinstance(schema, dict)
        schema["additionalProperties"] = True
        assert adapter.call_tool("save_report", {
            "report": "Valid", "unexpected": "blocked",
        }).decision == Decision.BLOCK
        with pytest.raises(ValueError, match="already registered"):
            adapter.register_tool(adapter._tools["save_report"])  # type: ignore[attr-defined]

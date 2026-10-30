from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from intent_integrity import (
    Decision,
    IntentContract,
    IntentIntegrityEngine,
    PlanStep,
    SQLiteEventStore,
    ValidationContext,
)
from intent_integrity.adapter import MAX_TOOL_ARGUMENT_BYTES, MAX_TOOL_RESULT_BYTES
from intent_integrity.integrations.async_tool_spec import AsyncToolSpecAdapter

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


class FakeAsyncToolSpec:
    def __init__(
        self,
        name: str = "report.create",
        *,
        consequential: bool = False,
        approval_required: bool = False,
    ) -> None:
        self.name = name
        self.consequential = consequential
        self.approval_required = approval_required
        self.validation_calls = 0

    def validate(self, arguments: dict[str, object]) -> object:
        self.validation_calls += 1
        if set(arguments) != {"report"}:
            raise ValueError("unexpected fields")
        report = arguments.get("report")
        if not isinstance(report, str) or not report.strip():
            raise ValueError("report must be a non-empty string")
        return {"report": report}


def make_adapter(handler: Any, spec: FakeAsyncToolSpec | None = None, action_id_factory=None):
    store = SQLiteEventStore(":memory:")
    contract = IntentContract(
        contract_id="async-tool-spec-consumer-test",
        version=1,
        goal="Create a report draft for user review.",
        permitted_actions=("report.create",),
        prohibited_actions=("report.publish",),
        acceptance_criteria=("Draft report saved",),
    )
    engine = IntentIntegrityEngine(store, clock=lambda: NOW)
    engine.start_task(contract)
    engine.record_plan(
        contract,
        (
            PlanStep(
                "draft",
                "Create a report draft",
                "report.create",
                acceptance_criteria=("Draft report saved",),
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

    adapter = AsyncToolSpecAdapter(
        engine,
        lambda: contract,
        context_provider,
        action_id_factory or action_id,
    )
    adapter.register_tool(spec or FakeAsyncToolSpec(), handler)
    return store, adapter


def test_async_tool_spec_executes_once_and_duplicate_is_blocked() -> None:
    calls: list[object] = []

    async def handler(validated: object) -> object:
        calls.append(validated)
        return {"saved": True}

    store, adapter = make_adapter(handler)
    try:
        first = asyncio.run(adapter.call_tool("report.create", {"report": "Quarterly draft"}))
        second = asyncio.run(adapter.call_tool("report.create", {"report": "Quarterly draft"}))
        assert first.decision == Decision.ALLOW and first.executed
        assert first.result == {"saved": True}
        assert second.decision == Decision.BLOCK
        assert "ACTION_ALREADY_CLAIMED" in second.reason_codes
        assert len(calls) == 1
    finally:
        store.close()


def test_async_tool_spec_validation_precedes_durable_claim() -> None:
    calls: list[object] = []

    async def handler(validated: object) -> object:
        calls.append(validated)
        return {"saved": True}

    spec = FakeAsyncToolSpec()
    store, adapter = make_adapter(handler, spec)
    try:
        result = asyncio.run(
            adapter.call_tool(
                "report.create",
                {"report": "Draft", "action_category": "report.publish"},
            )
        )
        assert result.decision == Decision.BLOCK
        assert "MALFORMED_INPUT" in result.reason_codes
        assert spec.validation_calls == 1
        assert calls == []
        assert not any(
            record.event.event_type.value == "ACTION_CLAIMED"
            for record in store.list_events("async-tool-spec-consumer-test")
        )
    finally:
        store.close()


def test_async_tool_spec_unknown_and_unpermitted_tools_fail_closed() -> None:
    async def handler(_validated: object) -> object:
        return {"saved": True}

    store, adapter = make_adapter(handler)
    try:
        unknown = asyncio.run(adapter.call_tool("unknown.tool", {"report": "Draft"}))
        unregistered = asyncio.run(
            adapter.call_tool("report.publish", {"report": "Draft"})
        )
        assert unknown.decision == Decision.BLOCK
        assert "UNKNOWN_TOOL" in unknown.reason_codes
        assert unregistered.decision == Decision.BLOCK
        assert "UNKNOWN_TOOL" in unregistered.reason_codes
    finally:
        store.close()


def test_async_tool_spec_rejects_consequential_and_approval_required_tools() -> None:
    async def handler(_validated: object) -> object:
        return {"sent": True}

    store, adapter = make_adapter(handler)
    try:
        with pytest.raises(ValueError, match="separately qualified approval"):
            adapter.register_tool(
                FakeAsyncToolSpec(
                    "email.send", consequential=True, approval_required=True
                ),
                handler,
            )
    finally:
        store.close()


def test_async_tool_spec_oversized_input_is_rejected_before_validation() -> None:
    calls: list[object] = []

    async def handler(validated: object) -> object:
        calls.append(validated)
        return {"saved": True}

    spec = FakeAsyncToolSpec()
    store, adapter = make_adapter(handler, spec)
    try:
        result = asyncio.run(
            adapter.call_tool(
                "report.create",
                {"report": "x" * (MAX_TOOL_ARGUMENT_BYTES + 1)},
            )
        )
        assert result.decision == Decision.BLOCK
        assert "MALFORMED_INPUT" in result.reason_codes
        assert spec.validation_calls == 0
        assert calls == []
    finally:
        store.close()


def test_async_tool_spec_oversized_result_becomes_unknown_and_cannot_retry() -> None:
    calls = 0

    async def handler(_validated: object) -> object:
        nonlocal calls
        calls += 1
        return "x" * (MAX_TOOL_RESULT_BYTES + 1)

    store, adapter = make_adapter(handler)
    try:
        first = asyncio.run(adapter.call_tool("report.create", {"report": "Draft"}))
        second = asyncio.run(adapter.call_tool("report.create", {"report": "Draft"}))
        assert first.outcome_unknown
        assert not first.executed
        assert "ACTION_OUTCOME_UNKNOWN" in first.reason_codes
        assert second.decision == Decision.BLOCK
        assert "ACTION_ALREADY_CLAIMED" in second.reason_codes
        assert calls == 1
        event_types = {
            record.event.event_type.value
            for record in store.list_events("async-tool-spec-consumer-test")
        }
        assert "ACTION_OUTCOME_UNKNOWN" in event_types
        assert "ACTION_SUCCEEDED" not in event_types
    finally:
        store.close()


def test_action_id_factory_mutation_cannot_change_validated_handler_input() -> None:
    calls: list[object] = []

    async def handler(validated: object) -> object:
        calls.append(validated)
        return {"saved": True}

    def mutating_action_id(_task: str, _name: str, args: dict[str, object]) -> str:
        args["report"] = "mutated after validation"
        return "snapshot-action"

    store, adapter = make_adapter(handler, action_id_factory=mutating_action_id)
    try:
        original = {"report": "validated report"}
        result = asyncio.run(adapter.call_tool("report.create", original))
        assert result.decision == Decision.ALLOW
        assert original == {"report": "validated report"}
        assert calls == [{"report": "validated report"}]
    finally:
        store.close()

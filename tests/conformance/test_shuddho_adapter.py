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
from intent_integrity.integrations.shuddho import ShuddhoConsumerAdapter

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


class FakeShuddhoToolSpec:
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

    def validate(self, arguments: dict[str, object]) -> object:
        if set(arguments) != {"report"}:
            raise ValueError("unexpected fields")
        report = arguments.get("report")
        if not isinstance(report, str) or not report.strip():
            raise ValueError("report must be a non-empty string")
        return {"report": report}


def make_consumer(handler: Any):
    store = SQLiteEventStore(":memory:")
    contract = IntentContract(
        contract_id="shuddho-consumer-test",
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

    consumer = ShuddhoConsumerAdapter(engine, lambda: contract, context_provider, action_id)
    consumer.register_tool(FakeShuddhoToolSpec(), handler)
    return store, consumer


def test_shuddho_async_tool_executes_once_and_duplicate_is_blocked() -> None:
    calls: list[object] = []

    async def handler(validated: object) -> object:
        calls.append(validated)
        return {"saved": True}

    store, consumer = make_consumer(handler)
    try:
        first = asyncio.run(consumer.call_tool("report.create", {"report": "Quarterly draft"}))
        second = asyncio.run(consumer.call_tool("report.create", {"report": "Quarterly draft"}))
        assert first.decision == Decision.ALLOW and first.executed
        assert first.result == {"saved": True}
        assert second.decision == Decision.BLOCK
        assert "ACTION_ALREADY_CLAIMED" in second.reason_codes
        assert len(calls) == 1
    finally:
        store.close()


def test_shuddho_schema_validation_precedes_durable_claim() -> None:
    calls: list[object] = []

    async def handler(validated: object) -> object:
        calls.append(validated)
        return {"saved": True}

    store, consumer = make_consumer(handler)
    try:
        result = asyncio.run(
            consumer.call_tool(
                "report.create",
                {"report": "Draft", "action_category": "report.publish"},
            )
        )
        assert result.decision == Decision.BLOCK
        assert "MALFORMED_INPUT" in result.reason_codes
        assert calls == []
        assert store.get_action_record(
            "shuddho-consumer-test",
            "report.create:" + hashlib.sha256(
                json.dumps(
                    {
                        "task": "shuddho-consumer-test",
                        "name": "report.create",
                        "args": {
                            "report": "Draft",
                            "action_category": "report.publish",
                        },
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            ).hexdigest(),
        ) is None
    finally:
        store.close()


def test_shuddho_unknown_tool_and_unpermitted_tool_fail_closed() -> None:
    async def handler(_validated: object) -> object:
        return {"saved": True}

    store, consumer = make_consumer(handler)
    try:
        unknown = asyncio.run(consumer.call_tool("unknown.tool", {"report": "Draft"}))
        unpermitted = asyncio.run(
            consumer.call_tool("report.publish", {"report": "Draft"})
        )
        assert unknown.decision == Decision.BLOCK
        assert "UNKNOWN_TOOL" in unknown.reason_codes
        assert unpermitted.decision == Decision.BLOCK
        assert "UNKNOWN_TOOL" in unpermitted.reason_codes
    finally:
        store.close()


def test_shuddho_consequential_tools_stay_on_native_approval_path() -> None:
    async def handler(_validated: object) -> object:
        return {"sent": True}

    store, consumer = make_consumer(handler)
    try:
        with pytest.raises(ValueError, match="native approved-action"):
            consumer.register_tool(
                FakeShuddhoToolSpec(
                    "email.send", consequential=True, approval_required=True
                ),
                handler,
            )
    finally:
        store.close()


def test_shuddho_ambiguous_async_outcome_cannot_be_retried() -> None:
    calls = 0

    async def handler(_validated: object) -> object:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider response was lost")

    store, consumer = make_consumer(handler)
    try:
        first = asyncio.run(consumer.call_tool("report.create", {"report": "Draft"}))
        second = asyncio.run(consumer.call_tool("report.create", {"report": "Draft"}))
        assert first.outcome_unknown
        assert not first.executed
        assert second.decision == Decision.BLOCK
        assert "ACTION_ALREADY_CLAIMED" in second.reason_codes
        assert calls == 1
    finally:
        store.close()

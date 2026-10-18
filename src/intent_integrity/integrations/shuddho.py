"""Async consumer bridge for Shuddho's server-owned ToolSpec contracts.

This module has no Shuddho runtime dependency. It accepts the ToolSpec protocol used by
Shuddho and keeps Pydantic input validation in front of the durable action claim.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol, cast

from intent_integrity.adapter import ToolCallResult
from intent_integrity.engine import IntentIntegrityEngine
from intent_integrity.models import (
    ActionRequest,
    Decision,
    IntentContract,
    ValidationContext,
)
from intent_integrity.store import ActionAlreadyClaimed

ContractProvider = Callable[[], IntentContract]
ContextProvider = Callable[[IntentContract], ValidationContext]
ActionIdFactory = Callable[[str, str, Mapping[str, object]], str]
AsyncShuddhoHandler = Callable[[object], Awaitable[object]]


class ShuddhoToolSpec(Protocol):
    """Structural subset of Shuddho's services.coworker.agent_tools.ToolSpec."""

    name: str
    consequential: bool
    approval_required: bool

    def validate(self, arguments: dict[str, object]) -> object:
        """Validate raw arguments using Shuddho's registered input model."""
        ...


class ShuddhoConsumerAdapter:
    """Guard asynchronous, non-consequential Shuddho tools at the execution boundary.

    Contract action categories are exact Shuddho tool names, not model-provided capabilities.
    Consequential and approval-required tools are rejected at registration so they remain on
    Shuddho's existing immutable ExternalAction and provider-reconciliation path.
    """

    def __init__(
        self,
        engine: IntentIntegrityEngine,
        contract_provider: ContractProvider,
        context_provider: ContextProvider,
        action_id_factory: ActionIdFactory,
    ) -> None:
        self._engine = engine
        self._contract_provider = contract_provider
        self._context_provider = context_provider
        self._action_id_factory = action_id_factory
        self._tools: dict[str, tuple[ShuddhoToolSpec, AsyncShuddhoHandler]] = {}

    def register_tool(
        self,
        spec: ShuddhoToolSpec,
        handler: AsyncShuddhoHandler,
    ) -> None:
        """Register a trusted Shuddho ToolSpec and its async execution function."""
        if not isinstance(spec.name, str) or not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,128}", spec.name
        ):
            raise ValueError("Invalid Shuddho tool name")
        if not callable(getattr(spec, "validate", None)):
            raise ValueError("Shuddho ToolSpec must provide validate(arguments)")
        if not isinstance(spec.consequential, bool) or not isinstance(
            spec.approval_required, bool
        ):
            raise ValueError("Shuddho ToolSpec must declare consequential and approval flags")
        if spec.consequential or spec.approval_required:
            raise ValueError(
                "Consequential or approval-required Shuddho tools must remain on the "
                "native approved-action and provider-reconciliation path"
            )
        if not callable(handler):
            raise ValueError("Shuddho handler must be callable")
        if spec.name in self._tools:
            raise ValueError(f"Shuddho tool {spec.name!r} is already registered")
        self._tools[spec.name] = (spec, handler)

    @staticmethod
    def _blocked(code: str, detail: str) -> ToolCallResult:
        return ToolCallResult(Decision.BLOCK, (code,), (detail,), False)

    async def call_tool(self, name: object, arguments: object) -> ToolCallResult:
        """Validate with Shuddho, then authorize and execute once through Intent Integrity."""
        if not isinstance(name, str) or not name.strip():
            return self._blocked("MALFORMED_TOOL_NAME", "Tool name must be a non-empty string.")
        registered = self._tools.get(name)
        if registered is None:
            return self._blocked("UNKNOWN_TOOL", "Unregistered Shuddho tool; nothing executed.")
        if not isinstance(arguments, dict) or any(
            not isinstance(key, str) for key in arguments
        ):
            return self._blocked("MALFORMED_INPUT", "Tool arguments must be a JSON object.")
        raw_arguments = cast(dict[str, object], arguments)
        try:
            json.dumps(raw_arguments, allow_nan=False)
        except (TypeError, ValueError):
            return self._blocked("MALFORMED_INPUT", "Arguments must contain finite JSON values.")

        spec, handler = registered
        try:
            validated_input = spec.validate(dict(raw_arguments))
        except Exception:
            return self._blocked(
                "MALFORMED_INPUT",
                "Shuddho's registered input model rejected the tool arguments.",
            )

        try:
            contract = self._contract_provider()
            if not isinstance(contract, IntentContract):
                raise TypeError("contract provider did not return IntentContract")
            if name not in contract.permitted_actions or name in contract.prohibited_actions:
                return self._blocked(
                    "TOOL_NOT_PERMITTED",
                    "The active intent contract does not permit this exact tool name.",
                )
            context = self._context_provider(contract)
            if not isinstance(context, ValidationContext):
                raise TypeError("context provider did not return ValidationContext")
            action_id = self._action_id_factory(contract.contract_id, name, raw_arguments)
            if not isinstance(action_id, str) or not action_id.strip():
                raise ValueError("action ID factory returned an empty ID")
        except Exception as exc:
            return self._blocked(
                "ADAPTER_FAILURE",
                f"Trusted adapter setup failed ({type(exc).__name__}); no tool was executed.",
            )

        async def execute() -> object:
            result = await handler(validated_input)
            json.dumps(result, allow_nan=False)
            return result

        try:
            outcome = await self._engine.async_guarded_execute(
                contract,
                ActionRequest(action_id=action_id, category=name),
                context,
                execute,
            )
        except ActionAlreadyClaimed:
            return self._blocked(
                "ACTION_ALREADY_CLAIMED",
                "This action ID was already claimed. Reconcile prior state before retrying.",
            )
        except Exception as exc:
            return ToolCallResult(
                Decision.BLOCK,
                ("ENGINE_FAILURE_OUTCOME_UNKNOWN",),
                (f"Engine failed ({type(exc).__name__}); reconcile before retrying.",),
                False,
                outcome_unknown=True,
            )

        return ToolCallResult(
            outcome.validation.decision,
            outcome.validation.reason_codes,
            outcome.validation.details,
            outcome.executed,
            outcome.value if outcome.executed else None,
            outcome.outcome_unknown,
        )

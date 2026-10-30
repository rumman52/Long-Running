"""Generic async ToolSpec bridge for independent host integrations.

The adapter depends only on a small structural protocol. It does not import or
require any external agent framework or runtime.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol, cast

from intent_integrity.adapter import (
    MAX_TOOL_ARGUMENT_BYTES,
    MAX_TOOL_RESULT_BYTES,
    ToolCallResult,
    _json_argument_error,
)
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
AsyncToolHandler = Callable[[object], Awaitable[object]]


class AsyncToolSpec(Protocol):
    """Minimal structural contract required by the optional async consumer bridge."""

    name: str
    consequential: bool
    approval_required: bool

    def validate(self, arguments: dict[str, object]) -> object:
        """Return a validated, JSON-compatible argument value."""
        ...


RegisteredTool = tuple[
    AsyncToolSpec, Callable[[dict[str, object]], object], AsyncToolHandler
]


def _snapshot_bounded_json(
    value: object,
    *,
    label: str,
    byte_limit: int = MAX_TOOL_ARGUMENT_BYTES,
) -> object:
    """Validate and snapshot a JSON value before it crosses a callback boundary."""
    structure_error = _json_argument_error(value)
    if structure_error is not None:
        raise ValueError(f"{label}: {structure_error}")
    try:
        serialized = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        encoded = serialized.encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeEncodeError) as exc:
        raise ValueError(f"{label} must contain finite JSON-compatible values") from exc
    if len(encoded) > byte_limit:
        raise ValueError(f"{label} exceeds the {byte_limit}-byte JSON limit")
    return json.loads(serialized)


class AsyncToolSpecAdapter:
    """Guard asynchronous ToolSpec handlers through the deterministic action gate.

    Consequential or approval-required tools are rejected at registration. Consumers
    must route those capabilities through a separately qualified approval and
    provider-reconciliation boundary.
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
        self._tools: dict[str, RegisteredTool] = {}

    def register_tool(self, spec: AsyncToolSpec, handler: AsyncToolHandler) -> None:
        """Register a trusted ToolSpec and its asynchronous execution handler."""
        if not isinstance(spec.name, str) or not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,128}", spec.name
        ):
            raise ValueError("Invalid ToolSpec name")
        if not callable(getattr(spec, "validate", None)):
            raise ValueError("ToolSpec must provide validate(arguments)")
        if not isinstance(spec.consequential, bool) or not isinstance(
            spec.approval_required, bool
        ):
            raise ValueError("ToolSpec must declare consequential and approval flags")
        if spec.consequential or spec.approval_required:
            raise ValueError(
                "Consequential or approval-required tools must use a separately "
                "qualified approval and provider-reconciliation boundary"
            )
        if not callable(handler):
            raise ValueError("Async tool handler must be callable")
        if spec.name in self._tools:
            raise ValueError(f"ToolSpec {spec.name!r} is already registered")
        validator = spec.validate
        self._tools[spec.name] = (spec, validator, handler)

    @staticmethod
    def _blocked(code: str, detail: str) -> ToolCallResult:
        return ToolCallResult(Decision.BLOCK, (code,), (detail,), False)

    async def call_tool(self, name: object, arguments: object) -> ToolCallResult:
        """Validate, authorize, and execute one bounded asynchronous tool call."""
        if not isinstance(name, str) or not name.strip():
            return self._blocked(
                "MALFORMED_TOOL_NAME", "Tool name must be a non-empty string."
            )
        registered = self._tools.get(name)
        if registered is None:
            return self._blocked(
                "UNKNOWN_TOOL", "Unregistered ToolSpec; nothing was executed."
            )
        if not isinstance(arguments, dict) or any(
            not isinstance(key, str) for key in arguments
        ):
            return self._blocked(
                "MALFORMED_INPUT", "Tool arguments must be a JSON object."
            )

        spec, validator, handler = registered
        try:
            registered_name = spec.name
            consequential = spec.consequential
            approval_required = spec.approval_required
        except Exception:
            return self._blocked(
                "TOOL_METADATA_INVALID",
                "ToolSpec metadata could not be read; execution is blocked.",
            )
        if registered_name != name:
            return self._blocked(
                "TOOL_METADATA_CHANGED",
                "Registered ToolSpec name changed; re-register the tool before use.",
            )
        if not isinstance(consequential, bool) or not isinstance(approval_required, bool):
            return self._blocked(
                "TOOL_METADATA_INVALID",
                "ToolSpec approval metadata is invalid; execution is blocked.",
            )
        if consequential or approval_required:
            return self._blocked(
                "TOOL_REQUIRES_APPROVAL",
                "ToolSpec approval metadata changed after registration; execution is blocked.",
            )

        try:
            raw_snapshot = _snapshot_bounded_json(arguments, label="Tool arguments")
            if not isinstance(raw_snapshot, dict):
                raise ValueError("Tool arguments must be a JSON object")
        except Exception:
            return self._blocked(
                "MALFORMED_INPUT",
                "Tool arguments must be a bounded JSON object.",
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
        except Exception as exc:
            return self._blocked(
                "ADAPTER_FAILURE",
                f"Trusted adapter setup failed ({type(exc).__name__}); no tool was executed.",
            )

        try:
            validation_arguments = _snapshot_bounded_json(
                raw_snapshot, label="ToolSpec validation arguments"
            )
            if not isinstance(validation_arguments, dict):
                raise ValueError("ToolSpec validation arguments must be an object")
            validated_input = validator(cast(dict[str, object], validation_arguments))
            validated_snapshot = _snapshot_bounded_json(
                validated_input, label="Validated ToolSpec input"
            )
            validated_json = json.dumps(
                validated_snapshot,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except Exception:
            return self._blocked(
                "MALFORMED_INPUT",
                "ToolSpec validation failed or returned invalid bounded JSON input.",
            )

        try:
            context = self._context_provider(contract)
            if not isinstance(context, ValidationContext):
                raise TypeError("context provider did not return ValidationContext")
            action_arguments = _snapshot_bounded_json(
                raw_snapshot, label="Action identity arguments"
            )
            if not isinstance(action_arguments, dict):
                raise TypeError("action identity arguments are not an object")
            action_id = self._action_id_factory(
                contract.contract_id, name, action_arguments
            )
            if not isinstance(action_id, str) or not action_id.strip():
                raise ValueError("action ID factory returned an empty ID")
        except Exception as exc:
            return self._blocked(
                "ADAPTER_FAILURE",
                f"Trusted adapter setup failed ({type(exc).__name__}); no tool was executed.",
            )

        async def execute() -> object:
            handler_input = json.loads(validated_json)
            result = await handler(handler_input)
            return _snapshot_bounded_json(
                result,
                label="Tool result",
                byte_limit=MAX_TOOL_RESULT_BYTES,
            )

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

        reason_codes = outcome.validation.reason_codes
        details = outcome.validation.details
        if outcome.outcome_unknown:
            reason_codes = (*reason_codes, "ACTION_OUTCOME_UNKNOWN")
            details = (*details, "The callback outcome is unknown; reconcile before retrying.")
        return ToolCallResult(
            outcome.validation.decision,
            reason_codes,
            details,
            outcome.executed,
            outcome.value if outcome.executed else None,
            outcome.outcome_unknown,
        )

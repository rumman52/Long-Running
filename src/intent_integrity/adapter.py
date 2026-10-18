"""Trusted tool registry that routes calls through IntentIntegrityEngine."""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from intent_integrity.engine import IntentIntegrityEngine
from intent_integrity.models import ActionRequest, Decision, IntentContract, ValidationContext
from intent_integrity.store import ActionAlreadyClaimed

ToolHandler = Callable[[dict[str, object]], object]
ContractProvider = Callable[[], IntentContract]
ContextProvider = Callable[[IntentContract], ValidationContext]
ActionIdFactory = Callable[[str, str, Mapping[str, object]], str]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """A tool definition registered by trusted host code."""

    name: str
    description: str
    action_category: str
    input_schema: dict[str, object]
    handler: ToolHandler

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", self.name):
            raise ValueError("Invalid tool name")
        if not self.description.strip() or not self.action_category.strip():
            raise ValueError("Tool description and action category must be non-empty")
        if self.input_schema.get("type") != "object":
            raise ValueError("Tool input schema must have type='object'")
        if not isinstance(self.input_schema.get("properties", {}), Mapping):
            raise ValueError("Tool schema properties must be an object")
        required = self.input_schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
            raise ValueError("Tool schema required must be an array of strings")
        try:
            json.dumps(self.input_schema, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("Tool schema must be JSON-serializable") from exc


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    """Structured tool decision and outcome."""

    decision: Decision
    reason_codes: tuple[str, ...]
    details: tuple[str, ...]
    executed: bool
    result: object | None = None
    outcome_unknown: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision.value,
            "reason_codes": list(self.reason_codes),
            "details": list(self.details),
            "executed": self.executed,
            "outcome_unknown": self.outcome_unknown,
            "result": self.result,
        }


def _validate_value(value: object, schema: Mapping[str, object], path: str) -> list[str]:
    """Validate the documented, intentionally limited JSON Schema subset."""
    expected = schema.get("type")
    valid = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "number": isinstance(value, (int, float)) and type(value) is not bool,
        "boolean": type(value) is bool,
        "null": value is None,
    }.get(expected, expected is None)
    if not valid:
        return [f"{path}: expected {expected}, got {type(value).__name__}"]
    errors: list[str] = []
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        errors.append(f"{path}: value is not in the allowed enum")

    if expected == "object" and isinstance(value, dict):
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            return [f"{path}: invalid registered properties"]
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    errors.append(f"{path}.{key}: required field is missing")
        additional = schema.get("additionalProperties", True)
        for key, child_value in value.items():
            if not isinstance(key, str):
                errors.append(f"{path}: object keys must be strings")
            elif key in properties:
                child_schema = properties[key]
                if isinstance(child_schema, Mapping):
                    errors.extend(_validate_value(child_value, child_schema, f"{path}.{key}"))
                else:
                    errors.append(f"{path}.{key}: invalid property schema")
            elif additional is False:
                errors.append(f"{path}.{key}: additional field is not allowed")
            elif isinstance(additional, Mapping):
                errors.extend(_validate_value(child_value, additional, f"{path}.{key}"))

    if expected == "array" and isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                errors.extend(_validate_value(item, item_schema, f"{path}[{index}]"))

    if expected == "string" and isinstance(value, str):
        minimum, maximum = schema.get("minLength"), schema.get("maxLength")
        if type(minimum) is int and len(value) < minimum:
            errors.append(f"{path}: string is shorter than minLength")
        if type(maximum) is int and len(value) > maximum:
            errors.append(f"{path}: string is longer than maxLength")
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                if re.search(pattern, value) is None:
                    errors.append(f"{path}: string does not match pattern")
            except re.error:
                errors.append(f"{path}: invalid pattern in registered schema")
    return errors


class GuardedToolAdapter:
    """Expose only trusted registered tools and gate every call before execution.

    A host must not expose the same consequential capability through another unguarded route.
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
        self._tools: dict[str, ToolDefinition] = {}

    def register_tool(self, definition: ToolDefinition) -> None:
        """Register a tool; copy the schema so later caller mutation cannot weaken validation."""
        if definition.name in self._tools:
            raise ValueError(f"Tool {definition.name!r} is already registered")
        schema = json.loads(json.dumps(definition.input_schema, allow_nan=False))
        self._tools[definition.name] = ToolDefinition(
            definition.name, definition.description, definition.action_category,
            schema, definition.handler,
        )

    def list_tools(self) -> list[dict[str, object]]:
        """Return tool metadata without exposing handlers or mutable internal schemas."""
        return [
            {
                "name": item.name,
                "description": item.description,
                "inputSchema": json.loads(json.dumps(item.input_schema)),
            }
            for item in self._tools.values()
        ]

    @staticmethod
    def _blocked(code: str, detail: str) -> ToolCallResult:
        return ToolCallResult(Decision.BLOCK, (code,), (detail,), False)

    def call_tool(self, name: object, arguments: object) -> ToolCallResult:
        """Validate identity and input, then delegate authorization and execution to the engine."""
        if not isinstance(name, str) or not name.strip():
            return self._blocked("MALFORMED_TOOL_NAME", "Tool name must be a non-empty string.")
        definition = self._tools.get(name)
        if definition is None:
            return self._blocked("UNKNOWN_TOOL", "Unregistered tool; nothing was executed.")
        if not isinstance(arguments, dict) or any(not isinstance(k, str) for k in arguments):
            return self._blocked("MALFORMED_INPUT", "Tool arguments must be a JSON object.")
        try:
            json.dumps(arguments, allow_nan=False)
        except (TypeError, ValueError):
            return self._blocked("MALFORMED_INPUT", "Arguments must contain finite JSON values.")
        input_errors = _validate_value(arguments, definition.input_schema, "$")
        if input_errors:
            return self._blocked("MALFORMED_INPUT", " ".join(input_errors))

        try:
            contract = self._contract_provider()
            if not isinstance(contract, IntentContract):
                raise TypeError("contract provider did not return IntentContract")
            context = self._context_provider(contract)
            if not isinstance(context, ValidationContext):
                raise TypeError("context provider did not return ValidationContext")
            action_id = self._action_id_factory(contract.contract_id, name, arguments)
            if not isinstance(action_id, str) or not action_id.strip():
                raise ValueError("action ID factory returned an empty ID")
        except Exception as exc:
            return self._blocked(
                "ADAPTER_FAILURE",
                f"Trusted adapter setup failed ({type(exc).__name__}); no tool was executed.",
            )

        action = ActionRequest(action_id=action_id, category=definition.action_category)

        def execute() -> object:
            result = definition.handler(dict(arguments))
            json.dumps(result, allow_nan=False)
            return result

        try:
            outcome = self._engine.guarded_execute(contract, action, context, execute)
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

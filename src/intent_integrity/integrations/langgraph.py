"""Optional LangGraph ToolNode adapter.

Only tools returned by build_langgraph_tools are wrapped. Hosts must not expose parallel,
unguarded copies of consequential tools.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from intent_integrity.adapter import GuardedToolAdapter, ToolDefinition


def _build_args_model(definition: ToolDefinition) -> Any:
    """Translate JSON Schema object fields into a strict Pydantic model.

    The Intent Integrity adapter remains the final validator. Unsupported JSON Schema
    constructs fail during setup instead of being silently weakened for the framework.
    """
    try:
        from pydantic import (  # type: ignore[import-not-found]
            ConfigDict,
            Field,
            StrictBool,
            StrictFloat,
            StrictInt,
            StrictStr,
            create_model,
        )
    except ImportError as exc:
        raise ImportError(
            "LangGraph integration requires the optional dependency: "
            "pip install -e '.[langgraph]'"
        ) from exc

    root = definition.input_schema
    if root.get("type") != "object":
        raise ValueError(f"Tool {definition.name!r} must use an object input schema")
    properties = root.get("properties", {})
    required = root.get("required", [])
    if not isinstance(properties, Mapping):
        raise ValueError(f"Tool {definition.name!r} has invalid properties")
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise ValueError(f"Tool {definition.name!r} has invalid required fields")
    if not set(required).issubset(properties):
        raise ValueError(f"Tool {definition.name!r} requires an undefined property")

    def annotation_for(schema: Mapping[str, object], field_name: str, depth: int = 0) -> Any:
        if depth > 8:
            raise ValueError("JSON Schema nesting exceeds the supported depth of 8")
        enum_values = schema.get("enum")
        if isinstance(enum_values, list):
            if not enum_values:
                raise ValueError(f"Field {field_name!r} has an empty enum")
            return Literal.__getitem__(tuple(enum_values))

        schema_type = schema.get("type")
        if schema_type == "string":
            return StrictStr
        if schema_type == "integer":
            return StrictInt
        if schema_type == "number":
            return StrictInt | StrictFloat
        if schema_type == "boolean":
            return StrictBool
        if schema_type == "null":
            return type(None)
        if schema_type == "array":
            items = schema.get("items")
            if not isinstance(items, Mapping):
                raise ValueError(f"Array field {field_name!r} must define item schema")
            return list[annotation_for(items, f"{field_name}Item", depth + 1)]  # type: ignore[misc]
        if schema_type == "object":
            nested_properties = schema.get("properties", {})
            nested_required = schema.get("required", [])
            if not isinstance(nested_properties, Mapping):
                raise ValueError(f"Nested field {field_name!r} has invalid properties")
            if not isinstance(nested_required, list) or any(
                not isinstance(item, str) for item in nested_required
            ):
                raise ValueError(f"Nested field {field_name!r} has invalid required fields")
            if not set(nested_required).issubset(nested_properties):
                raise ValueError(f"Nested field {field_name!r} requires an undefined property")
            nested_fields: dict[str, tuple[Any, Any]] = {}
            for child_name, child_schema in nested_properties.items():
                if not isinstance(child_name, str) or not isinstance(child_schema, Mapping):
                    raise ValueError(f"Nested field {field_name!r} has invalid property schema")
                child_type = annotation_for(child_schema, child_name, depth + 1)
                description = child_schema.get("description")
                default = (
                    Field(..., description=description)
                    if child_name in nested_required
                    else Field(default=None, description=description)
                )
                if child_name not in nested_required:
                    child_type = child_type | None
                nested_fields[child_name] = (child_type, default)
            return create_model(
                re.sub(r"[^A-Za-z0-9_]", "_", f"{definition.name}_{field_name}"),
                __config__=ConfigDict(extra="forbid", strict=True),
                **nested_fields,
            )
        raise ValueError(
            f"Tool {definition.name!r} uses unsupported schema type {schema_type!r}"
        )

    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, raw_schema in properties.items():
        if not isinstance(field_name, str) or not isinstance(raw_schema, Mapping):
            raise ValueError(f"Tool {definition.name!r} has an invalid property schema")
        field_type = annotation_for(raw_schema, field_name)
        description = raw_schema.get("description")
        default = (
            Field(..., description=description)
            if field_name in required
            else Field(default=None, description=description)
        )
        if field_name not in required:
            field_type = field_type | None
        fields[field_name] = (field_type, default)

    return create_model(
        re.sub(r"[^A-Za-z0-9_]", "_", f"{definition.name}_Input"),
        __config__=ConfigDict(extra="forbid", strict=True),
        **fields,
    )


def build_langgraph_tools(
    adapter: GuardedToolAdapter,
    definitions: Iterable[ToolDefinition],
) -> list[Any]:
    """Register trusted definitions and return LangChain tools suitable for LangGraph ToolNode."""
    try:
        from langchain_core.tools import StructuredTool  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "LangGraph integration requires the optional dependency: "
            "pip install -e '.[langgraph]'"
        ) from exc

    definitions = list(definitions)
    existing = {item.get("name") for item in adapter.list_tools()}
    if any(definition.name in existing for definition in definitions):
        raise ValueError("All LangGraph tool definitions must be new to this adapter")

    prepared: list[tuple[ToolDefinition, str, Any]] = []
    framework_names: set[str] = set()
    for definition in definitions:
        framework_name = re.sub(r"[^A-Za-z0-9_-]", "_", definition.name)
        if not framework_name or not re.match(r"^[A-Za-z0-9_-]{1,64}$", framework_name):
            raise ValueError(f"Tool {definition.name!r} cannot be mapped to a framework name")
        if framework_name in framework_names:
            raise ValueError("Two tool names collide after LangGraph name normalization")
        framework_names.add(framework_name)
        prepared.append((definition, framework_name, _build_args_model(definition)))

    tools: list[Any] = []
    for definition, framework_name, args_model in prepared:
        adapter.register_tool(definition)

        def make_runner(tool_name: str) -> Any:
            def run(**kwargs: object) -> str:
                result = adapter.call_tool(tool_name, dict(kwargs))
                return json.dumps(result.to_dict(), sort_keys=True, allow_nan=False)
            return run

        tools.append(
            StructuredTool.from_function(
                func=make_runner(definition.name),
                name=framework_name,
                description=definition.description,
                args_schema=args_model,
            )
        )
    return tools

"""Minimal MCP stdio transport for tools guarded by GuardedToolAdapter."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import TextIO

from intent_integrity.adapter import GuardedToolAdapter
from intent_integrity.models import Decision

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_MESSAGE_CHARS = 1_000_000
MAX_JSON_NESTING_DEPTH = 128


def _has_excessive_json_nesting(value: str) -> bool:
    """Bound JSON container nesting before json.loads reaches interpreter recursion limits."""
    depth = 0
    in_string = False
    escaped = False
    for character in value:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_NESTING_DEPTH:
                return True
        elif character in "]}" and depth:
            depth -= 1
    return False


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"Non-standard JSON numeric constant: {value}")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON numbers must be finite")
    return parsed


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


class MCPStdioServer:
    """Newline-delimited JSON-RPC subset: initialize, ping, tools/list, and tools/call."""

    def __init__(
        self, adapter: GuardedToolAdapter, *, name: str = "intent-integrity", version: str = "0.2.0"
    ) -> None:
        if not name.strip() or not version.strip():
            raise ValueError("Server name and version must be non-empty")
        self._adapter = adapter
        self._name = name
        self._version = version

    @staticmethod
    def _error(request_id: object, code: int, message: str) -> dict[str, object]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def handle_message(self, message: object) -> dict[str, object] | None:
        if not isinstance(message, dict):
            return self._error(None, -32600, "Invalid Request")
        request_id = message.get("id")
        method = message.get("method")
        has_id = "id" in message
        if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid Request")
        if has_id and (
            request_id is not None
            and (
                not isinstance(request_id, (str, int, float))
                or type(request_id) is bool
                or (isinstance(request_id, float) and not math.isfinite(request_id))
            )
        ):
            return self._error(None, -32600, "Invalid Request")
        if not has_id:
            return None
        params = message.get("params", {})
        if not isinstance(params, Mapping):
            return self._error(request_id, -32602, "Invalid params")

        if method == "initialize":
            requested = params.get("protocolVersion")
            protocol = (
                requested
                if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS
                else SUPPORTED_PROTOCOL_VERSIONS[0]
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": protocol,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self._name, "version": self._version},
                    "instructions": (
                        "Tools exposed here pass through the Intent Integrity gate. Tools outside "
                        "this server are not protected. Reconcile ambiguous outcomes before retry."
                    ),
                },
            }
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": self._adapter.list_tools()},
            }
        if method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str) or not name.strip():
                return self._error(request_id, -32602, "tools/call requires a non-empty name")
            result = self._adapter.call_tool(name, params.get("arguments", {}))
            is_error = (
                result.decision != Decision.ALLOW or not result.executed or result.outcome_unknown
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result.to_dict()),
                    }],
                    "isError": is_error,
                },
            }
        if method.startswith("notifications/"):
            return None
        return self._error(request_id, -32601, "Method not found")

    def serve_stdio(self, input_stream: TextIO, output_stream: TextIO) -> None:
        """Serve bounded newline-delimited JSON-RPC; stdout contains protocol messages only."""
        while True:
            line = input_stream.readline(MAX_MESSAGE_CHARS + 1)
            if line == "":
                break

            response: dict[str, object] | None = None
            if len(line) > MAX_MESSAGE_CHARS:
                # Consume the rest of this record so a following valid request remains usable.
                if not line.endswith("\n"):
                    while True:
                        remainder = input_stream.readline(MAX_MESSAGE_CHARS + 1)
                        if remainder == "" or remainder.endswith("\n"):
                            break
                response = self._error(None, -32600, "Request exceeds maximum message size")
            elif not line.strip():
                continue
            elif _has_excessive_json_nesting(line):
                response = self._error(None, -32700, "Parse error")
            else:
                try:
                    message = json.loads(
                        line,
                        parse_constant=_reject_json_constant,
                        parse_float=_parse_finite_float,
                        object_pairs_hook=_reject_duplicate_keys,
                    )
                    response = self.handle_message(message)
                except (json.JSONDecodeError, ValueError, RecursionError):
                    response = self._error(None, -32700, "Parse error")

            if response is not None:
                output_stream.write(
                    json.dumps(
                        response,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    + "\n"
                )
                output_stream.flush()

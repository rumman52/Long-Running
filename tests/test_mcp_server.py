from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from io import StringIO

from intent_integrity import (
    GuardedToolAdapter, IntentContract, IntentIntegrityEngine, MCPStdioServer,
    PlanStep, SQLiteEventStore, ToolDefinition, ValidationContext,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def make_server(store: SQLiteEventStore):
    active = IntentContract(
        contract_id="mcp-test-task", version=1,
        goal="Prepare a report; never delete source data.",
        permitted_actions=("write_report",), prohibited_actions=("delete_source",),
        acceptance_criteria=("Report is accurate",),
    )
    engine = IntentIntegrityEngine(store, clock=lambda: NOW)
    engine.start_task(active)
    engine.record_plan(active, (
        PlanStep("draft", "Draft report", "write_report",
                 acceptance_criteria=("Report is accurate",)),
    ))
    calls: list[dict[str, object]] = []

    def action_id(task: str, name: str, args: object) -> str:
        data = json.dumps({"task": task, "name": name, "args": args}, sort_keys=True)
        return f"{name}:{hashlib.sha256(data.encode()).hexdigest()}"

    adapter = GuardedToolAdapter(
        engine, lambda: active,
        lambda current: ValidationContext(
            now=NOW, evidence={}, approvals={}, active_contract_version=current.version,
        ),
        action_id,
    )
    schema = {"type": "object", "properties": {"report": {"type": "string"}},
              "required": ["report"], "additionalProperties": False}
    adapter.register_tool(ToolDefinition(
        "save_report", "Save a draft", "write_report", schema,
        lambda args: (calls.append(dict(args)) or {"saved": True}),
    ))
    adapter.register_tool(ToolDefinition(
        "delete_source", "Prohibited demo tool", "delete_source",
        {"type": "object", "properties": {"target": {"type": "string"}},
         "required": ["target"], "additionalProperties": False},
        lambda args: (calls.append(dict(args)) or {"deleted": True}),
    ))
    return MCPStdioServer(adapter), calls


def test_initialize_and_tool_listing() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        init = server.handle_message({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        })
        listed = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert init is not None and listed is not None
        assert init["result"]["protocolVersion"] == "2025-03-26"  # type: ignore[index]
        result = listed["result"]  # type: ignore[assignment]
        assert isinstance(result, dict)
        tools = result["tools"]
        assert isinstance(tools, list)
        assert {tool["name"] for tool in tools} == {"save_report", "delete_source"}


def test_blocked_mcp_call_does_not_reach_handler() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, calls = make_server(store)
        reply = server.handle_message({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "delete_source", "arguments": {"target": "source.csv"}},
        })
        assert reply is not None
        result = reply["result"]
        assert isinstance(result, dict) and result["isError"] is True
        content = result["content"]
        assert isinstance(content, list) and isinstance(content[0], dict)
        payload = json.loads(content[0]["text"])
        assert payload["decision"] == "BLOCK" and payload["executed"] is False
        assert calls == []


def test_allowed_mcp_call_returns_structured_result() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, calls = make_server(store)
        reply = server.handle_message({
            "jsonrpc": "2.0", "id": "call-1", "method": "tools/call",
            "params": {"name": "save_report", "arguments": {"report": "Draft"}},
        })
        assert reply is not None
        result = reply["result"]
        assert isinstance(result, dict) and result["isError"] is False
        content = result["content"]
        assert isinstance(content, list) and isinstance(content[0], dict)
        payload = json.loads(content[0]["text"])
        assert payload["decision"] == "ALLOW" and payload["executed"] is True
        assert calls == [{"report": "Draft"}]


def test_stdio_parse_errors_and_notifications() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        assert server.handle_message({
            "jsonrpc": "2.0", "method": "notifications/initialized",
        }) is None
        output = StringIO()
        server.serve_stdio(StringIO("{not-json}\n"), output)
        assert json.loads(output.getvalue())["error"]["code"] == -32700


def test_unknown_method_returns_json_rpc_error() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        reply = server.handle_message({"jsonrpc": "2.0", "id": 4, "method": "tools/delete"})
        assert reply is not None and reply["error"]["code"] == -32601


def test_stdio_rejects_non_finite_json_constants_and_continues() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        output = StringIO()
        invalid_requests = (
            '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"n":NaN}}\n'
            '{"jsonrpc":"2.0","id":2,"method":"ping","params":{"n":Infinity}}\n'
            '{"jsonrpc":"2.0","id":3,"method":"ping","params":{"n":-Infinity}}\n'
            '{"jsonrpc":"2.0","id":4,"method":"ping","params":{"n":1e999}}\n'
        )
        server.serve_stdio(
            StringIO(invalid_requests + '{"jsonrpc":"2.0","id":5,"method":"ping"}\n'),
            output,
        )
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        assert [reply["error"]["code"] for reply in replies[:4]] == [-32700] * 4
        assert replies[4]["result"] == {}


def test_stdio_rejects_duplicate_json_object_keys() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        output = StringIO()
        server.serve_stdio(
            StringIO(
                '{"jsonrpc":"2.0","id":1,"method":"ping","method":"initialize"}\n'
            ),
            output,
        )
        reply = json.loads(output.getvalue())
        assert reply["error"]["code"] == -32700


def test_stdio_rejects_duplicate_keys_inside_nested_objects() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        output = StringIO()
        server.serve_stdio(
            StringIO(
                '{"jsonrpc":"2.0","id":1,"method":"ping","params":'
                '{"nested":{"mode":"safe","mode":"unsafe"}}}\n'
                '{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
            ),
            output,
        )
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        assert replies[0]["error"]["code"] == -32700
        assert replies[1]["result"] == {}


def test_stdio_rejects_oversized_line_and_processes_next_request() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        oversized = (
            '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"padding":"'
            + ("x" * 1_000_001)
            + '"}}\n'
        )
        output = StringIO()
        server.serve_stdio(
            StringIO(oversized + '{"jsonrpc":"2.0","id":2,"method":"ping"}\n'),
            output,
        )
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        assert replies[0]["error"]["code"] == -32600
        assert replies[1]["result"] == {}


def test_stdio_rejects_excessive_json_nesting_and_continues() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        deeply_nested = "[" * 1_200 + "0" + "]" * 1_200
        output = StringIO()
        server.serve_stdio(
            StringIO(
                '{"jsonrpc":"2.0","id":1,"method":"ping","params":{"nested":'
                + deeply_nested
                + '}}\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
            ),
            output,
        )
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        assert replies[0]["error"]["code"] == -32700
        assert replies[1]["result"] == {}

def test_stdio_ignores_deep_brackets_inside_json_strings() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        payload = 'quoted "text" with slash \\\\ ' + "[" * 1_200 + "]" * 1_200
        request = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {"text": payload}}
        )
        output = StringIO()
        server.serve_stdio(StringIO(request + "\n"), output)
        reply = json.loads(output.getvalue())
        assert reply["result"] == {}


def test_handle_message_rejects_non_finite_request_id() -> None:
    with SQLiteEventStore(":memory:") as store:
        server, _ = make_server(store)
        for request_id in (float("nan"), float("inf"), float("-inf")):
            reply = server.handle_message(
                {"jsonrpc": "2.0", "id": request_id, "method": "ping"}
            )
            assert reply is not None
            assert reply["error"]["code"] == -32600
            assert reply["id"] is None

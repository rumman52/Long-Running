# Guarded Tool Adapter and MCP stdio integration

## Purpose

The engine already provides a guarded callback. This milestone adds a host-owned tool registry and a minimal MCP stdio transport so a host can expose selected tools through that gate.

## Execution boundary

1. The host authenticates the user and supplies the authorized active contract.
2. Trusted application code registers tool names, schemas, fixed action categories, and handlers.
3. The adapter validates JSON arguments and asks the engine to authorize the action against trusted current context.
4. Only an `ALLOW` result reaches the registered callback; action claims are durable before execution.
5. Duplicate IDs are blocked. Callback exceptions and uncertain engine failures must be reconciled rather than blindly retried.

The adapter cannot protect tools exposed by a separate unguarded path. The host must ensure every consequential capability is routed through this boundary.

## Run the local demonstration

```bash
python -m pip install -e ".[dev]"
python examples/guarded_mcp_server.py
```

This demonstration uses fake local callbacks and a temporary SQLite database. It does not contact external services. Standard output is reserved for newline-delimited JSON-RPC messages. Try an `initialize`, `tools/list`, or `tools/call` request, one JSON object per line.

## Input-boundary hardening status

PR #18 merged the bounded-input implementation and adversarial LangGraph regression into main at commit `330e5acf3f17e2b0c5b830570b42c85f9a39e07c`. Merged head `0c91e34fa8b57a86673b22f05ab7a6a7e6efb545` passed Python CI [#41114350260](https://github.com/rumman52/Long-Running/actions/runs/41114350260) and dependency audit [#41114350246](https://github.com/rumman52/Long-Running/actions/runs/41114350246). No independent review was recorded. Follow-up PR #19 rechecks mutable ToolSpec approval metadata after registration; its exact-head CI is pending.

Candidate behavior:

- MCP stdio records are limited to 1,000,000 characters, and JSON container nesting is explicitly capped at 128 before decoding. The scanner ignores brackets and braces inside escaped JSON strings.
- Duplicate keys at any object depth, NaN/Infinity, exponent-overflow floats, malformed JSON, excessive nesting, and oversized records are rejected as parse errors. The stdio loop continues with the next record.
- Guarded-tool arguments and returned results are limited to 1,000,000 compact UTF-8 JSON bytes, depth 64, and 100,000 JSON nodes.
- Cyclic, non-finite, non-JSON, oversized, or excessively nested arguments fail before the action-ID factory and handler. Validated arguments are snapshotted before trusted callbacks.
- If a callback has already run but its result is invalid or exceeds the result bound, the engine records an unknown outcome and does not return the oversized result. The host must reconcile before retrying; it must not assume the action failed.
- The adversarial LangGraph test uses a compiled `StateGraph` and `ToolNode` with a scripted agent node that deliberately follows prompt-injection-shaped tool output. The prohibited callback remains uninvoked. This is deterministic framework-boundary evidence, not live-LLM qualification.

These controls are merged on main, but they have not received independent security review or live-host qualification. They do not establish full MCP protocol/client conformance.

## Scope and security limitations

- This is a practical subset of JSON Schema validation; use a conformant validator for complex schemas.
- The MCP wrapper supports only initialization, ping, tool listing/calls, and notification suppression. `tests/test_mcp_sdk_conformance.py` exercises initialize, list, allowed calls, and blocked calls through the official MCP Python SDK 2.x client. This is a focused SDK smoke test, not a complete MCP protocol/client conformance suite.
- No authentication handshake, resource/prompt APIs, cancellation, progress, transport security, or dynamic tool-list notifications are implemented.
- Provider-specific outcome lookup, conditional operations, and reconciliation after a timeout/crash remain future work.
- Multi-process SQLite concurrency and crash/reconciliation fault injection are covered by the persistence and reconciliation suites. LangGraph ToolNode and optional structural async ToolSpec adapter tests are local conformance checks; no external host runtime is bundled or required.
- A live LLM-driven host adversarial evaluation, a broader MCP protocol/client matrix, live Gemma measurements on independently labelled data, and independent external security review remain outstanding.

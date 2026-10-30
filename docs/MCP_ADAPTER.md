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

## Scope and security limitations

- This is a practical subset of JSON Schema validation; use a conformant validator for complex schemas.
- The MCP wrapper supports only initialization, ping, tool listing/calls, and notification suppression. `tests/test_mcp_sdk_conformance.py` exercises initialize, list, allowed calls, and blocked calls through the official MCP Python SDK 2.x client. This is a focused SDK smoke test, not a complete MCP protocol/client conformance suite.
- No authentication handshake, resource/prompt APIs, cancellation, progress, transport security, or dynamic tool-list notifications are implemented.
- Provider-specific outcome lookup, conditional operations, and reconciliation after a timeout/crash remain future work.
- Multi-process SQLite concurrency and crash/reconciliation fault injection are covered by the persistence and reconciliation suites. LangGraph ToolNode and Shuddho adapter-level tests are present, but the Shuddho bridge is not wired into its deployed runtime.
- Real-host adversarial bypass/prompt-injection evaluation, a broader MCP protocol/client matrix, live Gemma measurements on independently labelled data, and independent external security review remain outstanding.

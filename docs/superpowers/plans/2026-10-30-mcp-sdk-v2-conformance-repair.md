# MCP Python SDK v2 conformance repair

**Date:** 2026-10-30  
**Repository:** https://github.com/rumman52/Long-Running  
**Base:** `9f99ace2c4040839fae1f17268676628584ee399`  
**Branch:** `fix/mcp-sdk-v2-conformance-20261030`

## Root cause

The latest main-branch Python CI run failed on every supported Python version at
`tests/test_mcp_sdk_conformance.py`. The test accessed
`InitializeResult.serverInfo`, a camelCase attribute that is not present in the
MCP Python SDK 2.3.0 Pydantic model. The SDK v2 migration exposes negotiated
server metadata through `ClientSession.server_info`.

The failing run reported 116 passed, 1 failed, and 1 skipped on Python 3.11.
The first correction removed the `serverInfo` failure; the next exact-head CI run then exposed the second stale camelCase access, `CallToolResult.isError`. The v2 client requires `is_error`. The original failure occurred on Python 3.11–3.15.

## Implementation decisions

- Keep the MCP server implementation unchanged; the wire response was valid.
- Target the current MCP Python SDK v2 API explicitly in the development extra.
- Read the negotiated server metadata from `session.server_info` after
  `session.initialize()`, and assert both the server name and version, and inspect allowed/blocked call outcomes through `CallToolResult.is_error`.
- Update MCP adapter documentation to distinguish the focused SDK smoke test
  from full protocol conformance and to remove stale statements about already
  implemented persistence/framework tests.

## Verification

1. Re-run the focused SDK conformance test through GitHub Actions.
2. Run the complete Python test suite on Python 3.11–3.14.
3. Run the runtime examples, Ruff, and strict mypy through the existing CI.
4. Confirm the M7 synthetic evaluation, LangGraph conformance, and dependency
   audit jobs remain green.

## Explicitly out of scope

This repair does not claim full MCP protocol conformance, live external-host
integration, real-host adversarial qualification, live Gemma accuracy, an
independent external security review, maintainer license approval, or a public
release. Those remain separate acceptance gates in `docs/ROADMAP.md`.

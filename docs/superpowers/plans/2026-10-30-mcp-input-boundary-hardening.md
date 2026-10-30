# MCP Input Boundary Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound untrusted JSON-RPC and tool arguments, reject ambiguous/non-standard JSON, and add regression coverage for hostile input at the real LangGraph ToolNode boundary.

**Architecture:** Keep the deterministic validator and tool registry as the final authorization gate. Add transport-level line limits and strict JSON decoding in the MCP stdio server, plus bounded JSON argument validation in the generic guarded adapter. Use the existing LangGraph ToolNode integration to exercise prompt-injection-shaped tool output followed by a prohibited tool call.

**Tech Stack:** Python 3.11+, stdlib json/math, pytest, LangGraph optional extra.

**Spec:** `docs/ROADMAP.md` M4 and `docs/THREAT_MODEL.md`.

## Global Constraints

- Core runtime dependencies remain empty.
- Keep Python 3.11–3.14 as the supported CI matrix.
- Preserve the MCP JSON-RPC wire format and existing SDK v2 conformance behavior.
- Malformed, oversized, non-finite, duplicate-key, or excessively nested input must fail closed before tool execution.
- Never treat prompt-injection text in a tool result as trusted authorization.
- Do not add a dependency solely for JSON parsing or size checks.

## Review Focus

- Oversized newline-delimited requests and recovery to the next valid request.
- Non-standard numeric constants and exponent overflow (NaN, Infinity, 1e999).
- Duplicate keys at any object nesting level.
- Excessively nested JSON causing decoder/serializer recursion failures.
- Oversized or cyclic Python argument objects supplied directly to the adapter.
- Prompt-injection-shaped output followed by an attempted prohibited LangGraph tool call.

---

### Task 1: Strict bounded MCP stdio input

**Files:**
- Modify: `src/intent_integrity/mcp_server.py`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Add a documented `MAX_MESSAGE_CHARS` constant (1,000,000).
- Reject duplicate object keys, non-standard JSON constants, and non-finite parsed floats.
- Read each line with a bounded `readline` and drain oversized records before processing the next request.
- Convert malformed/recursive input to JSON-RPC parse errors without terminating the stdio loop.

- [ ] Write tests for non-finite values, duplicate keys, overlong requests, and valid requests following rejected input.
- [ ] Run the focused tests and confirm the new cases fail for the current implementation.
- [ ] Implement the bounded decoder and line reader.
- [ ] Re-run focused tests and the full Python CI matrix.

### Task 2: Bound generic guarded tool arguments

**Files:**
- Modify: `src/intent_integrity/adapter.py`
- Test: `tests/test_adapter.py`

**Interfaces:**
- Add a 1,000,000-byte serialized argument limit and maximum JSON depth of 64.
- Reject cyclic, non-finite, oversized, or excessively nested argument objects with a structured `MALFORMED_INPUT` result.
- Do not invoke the action-ID factory or handler after an input-boundary rejection.

- [ ] Write regression tests and confirm they fail against the current adapter.
- [ ] Implement iterative depth checking and bounded serialization.
- [ ] Verify the action callback remains untouched for rejected input.
- [ ] Run adapter, MCP, full test, Ruff, and mypy checks.

### Task 3: LangGraph adversarial tool-result conformance

**Files:**
- Modify: `tests/conformance/test_langgraph_adapter.py`

**Interfaces:**
- Extend the local ToolNode fixture with a registered prohibited action.
- Return prompt-injection-shaped text from an otherwise permitted tool.
- Attempt the prohibited action through the same compiled ToolNode and verify deterministic policy blocks it before the callback.

- [ ] Add the adversarial conformance test.
- [ ] Run the LangGraph CI job and verify the allowed tool executes while the prohibited tool remains unexecuted.

### Task 4: Document security limits

**Files:**
- Modify: `docs/MCP_ADAPTER.md`
- Modify: `docs/THREAT_MODEL.md`
- Modify: `docs/ROADMAP.md`

- [ ] Document input bounds and hostile-input behavior.
- [ ] Distinguish framework-level adversarial evidence from live LLM/host qualification.
- [ ] Record any remaining external qualification honestly.
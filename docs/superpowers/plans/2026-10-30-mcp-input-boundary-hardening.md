# MCP Input Boundary Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound untrusted JSON-RPC records, generic guarded-tool arguments and results; reject ambiguous/non-standard JSON; and test hostile tool output at the LangGraph execution boundary.

**Architecture:** Keep the deterministic validator and tool registry as the final authorization gate. Add transport-level line and nesting limits with strict JSON decoding, plus bounded JSON argument/result validation in the generic guarded adapter. Use a compiled LangGraph graph with a scripted deterministic agent to exercise prompt-injection-shaped tool output.

**Tech Stack:** Python 3.11+, stdlib json/math, pytest, LangGraph optional extra.

**Spec:** `docs/ROADMAP.md` M4 and `docs/THREAT_MODEL.md`.

## Global Constraints

- Core runtime dependencies remain empty.
- Keep Python 3.11–3.14 as the supported CI matrix.
- Preserve the MCP JSON-RPC wire format and existing SDK v2 conformance behavior.
- Malformed, oversized, non-finite, duplicate-key, cyclic, non-JSON, or excessively nested input must fail closed before tool execution.
- Never treat prompt-injection text in a tool result as trusted authorization.
- If a callback has already executed but its result is invalid or oversized, record UNKNOWN and require reconciliation; never recommend blind retry.
- Do not add a dependency solely for JSON parsing or size checks.

## Review Focus

- Oversized newline-delimited requests and recovery to the next valid request.
- Explicit JSON container nesting limit before the interpreter parser recursion limit.
- Non-standard numeric constants and exponent overflow (NaN, Infinity, 1e999).
- Duplicate keys at any object nesting level.
- Oversized, cyclic, non-finite, deeply nested, and non-JSON Python argument objects supplied directly to the adapter.
- Oversized/invalid callback results after execution and UNKNOWN outcome handling.
- Prompt injection in an allowed tool result followed by an attempted prohibited LangGraph tool call.

---

### Task 1: Strict bounded MCP stdio input

**Files:**
- Modify: `src/intent_integrity/mcp_server.py`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- `MAX_MESSAGE_CHARS = 1_000_000`.
- `MAX_JSON_NESTING_DEPTH = 128`, checked by a string/escape-aware scan before `json.loads`.
- Reject duplicate object keys, non-standard JSON constants, non-finite parsed floats, and excessive nesting.
- Read each line with a bounded `readline` and drain oversized records before processing the next request.
- Convert malformed input to JSON-RPC parse errors without terminating the stdio loop.

- [x] Write tests for non-finite values, duplicate keys (including nested keys), overlong requests, excessive nesting, bracket characters inside escaped strings, and valid requests following rejected input.
- [ ] Capture a CI run on the test-only commits showing the initial RED state. The branch history is test-first, but no CI result for the test-only stage is recorded; do not claim a verified RED run.
- [x] Implement the bounded decoder, explicit nesting scan, and line reader.
- [x] Re-run the full Python matrix. Exact-head Python CI [#41104798481](https://github.com/rumman52/Long-Running/actions/runs/41104798481) passed.

### Task 2: Bound generic guarded tool arguments and results

**Files:**
- Modify: `src/intent_integrity/adapter.py`
- Test: `tests/test_adapter.py`

**Interfaces:**
- Add a 1,000,000-byte compact UTF-8 JSON argument and result limit.
- Enforce maximum JSON depth 64 and maximum 100,000 JSON nodes.
- Reject cyclic, non-finite, oversized, or non-JSON arguments before the action-ID factory and handler.
- Snapshot validated arguments before calling trusted callbacks.
- If a callback runs but its result is invalid/oversized, record an UNKNOWN outcome and do not return the result to the host.

- [x] Write regression tests for oversize, depth, node count, cycles, non-finite values, UTF-8 byte accounting, callback snapshot mutation, and invalid/oversized results.
- [ ] Capture a CI run on the test-only commits showing the initial RED state. The branch history is test-first, but no CI result for the test-only stage is recorded; do not claim a verified RED run.
- [x] Implement iterative bounded traversal, compact JSON snapshots, and result validation.
- [x] Verify the action-ID factory and handler remain untouched for rejected input; verify an executed callback with an oversized result is recorded UNKNOWN.
- [x] Run adapter, MCP, full test, Ruff, mypy, and Python matrix checks through exact-head CI #41104798481.

### Task 3: LangGraph adversarial tool-result conformance

**Files:**
- Modify: `tests/conformance/test_langgraph_adapter.py`

**Interfaces:**
- Use the real LangGraph `StateGraph` and `ToolNode` execution path.
- Use a deterministic scripted agent node to consume prompt-injection-shaped output from an allowed tool and deliberately request a prohibited action.
- Verify the guarded adapter blocks the prohibited callback.

- [x] Add the compiled-graph adversarial conformance test.
- [x] Run LangGraph conformance in exact-head CI #41104798481; it passed.
- [ ] Run a live LLM-driven host assessment and audit alternate unguarded consumer routes. The scripted agent test is not a live-model or universal-host security qualification.

### Task 4: Document security limits

**Files:**
- Modify: `docs/MCP_ADAPTER.md`
- Modify: `docs/THREAT_MODEL.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/CROSS_FRAMEWORK_CONFORMANCE.md`
- Modify: `docs/RELEASE_READINESS.md`
- Modify: `CHANGELOG.md`

- [x] Document transport, argument, and result bounds and hostile-input behavior.
- [x] Distinguish deterministic framework-level adversarial evidence from live LLM/host qualification.
- [x] Record remaining independent-review, MCP-client, provider, live Gemma, license, lockfile, governance, and release gates.

## Verification evidence

- Candidate head: `267ed56d9ad3d1d0f1ebe922a9f9670163e19522`.
- Python CI: [#41104798481](https://github.com/rumman52/Long-Running/actions/runs/41104798481) — success across Python 3.11–3.14, Python 3.15 best-effort, Ruff, strict mypy, LangGraph conformance, and M7 fixture evaluation.
- Dependency audit: [#41104798516](https://github.com/rumman52/Long-Running/actions/runs/41104798516) — success.
- PR #16 remains draft and unmerged; submitted independent reviews: 0.
- This plan records candidate-branch evidence only. It does not claim full MCP protocol conformance, live LLM host security, provider qualification, or production certification.

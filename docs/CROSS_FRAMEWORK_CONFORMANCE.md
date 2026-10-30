# Cross-Framework Conformance and Evaluation

## Scope

M7 makes the framework boundary explicit and provides a reproducible evaluation harness. Long-Running is a standalone, framework-neutral library. Framework adapters are optional integration surfaces; no external agent product, service, database, or deployed runtime is required to install or use the core package.

An adapter is protective only when the consumer host routes every relevant action through it and does not expose an equivalent unguarded path.

## Compatibility matrix

| Consumer / framework | Adapter | Evidence in this repository | Compatibility limit |
|---|---|---|---|
| Plain Python host | GuardedToolAdapter | Unit tests cover allow, block, malformed input, unknown tools, duplicate claims, and callback failure | Host must own the registry and route all protected calls through it |
| Optional async ToolSpec consumer | Structural async ToolSpec bridge | Local protocol-fixture tests cover validation, authorization, duplicate claims, and ambiguous outcomes | Adapter-level only; no external runtime dependency or deployment integration is required |
| LangGraph | build_langgraph_tools + ToolNode | Optional CI job invokes wrapped tools through LangGraph ToolNode and verifies allowed execution, duplicate blocking, and schema rejection | Tests the ToolNode boundary, not a live LLM, complete graph, or every LangGraph version/provider combination |
| MCP stdio | MCPStdioServer | Local JSON-RPC subset tests and official MCP Python SDK 2.x smoke tests | Not full official MCP protocol/client conformance |

The LangGraph integration converts supported JSON Schema object definitions into strict Pydantic tool schemas. It fails at setup for unsupported schema constructs rather than silently weakening the framework-facing schema. Long-Running's own input validation remains the final gate.

## Install and test

Base adapter tests:

```bash
python -m pip install -e ".[dev]"
pytest tests/test_adapter.py tests/test_mcp_server.py -q
```

Optional LangGraph conformance:

```bash
python -m pip install -e ".[dev,langgraph]"
pytest tests/conformance/test_langgraph_adapter.py -q
```

Run the full suite and quality checks:

```bash
pytest
ruff check src tests examples benchmarks
mypy src/intent_integrity
```

Run the deterministic fixture harness:

```bash
python benchmarks/evaluate_m7.py --output artifacts/m7-evaluation.json
```

Run the hybrid harness with the M6 Gemma/Ollama provider:

```bash
ollama pull gemma3:4b
ollama serve
python benchmarks/evaluate_m7.py --semantic-provider gemma-ollama --model gemma3:4b --output artifacts/m7-gemma-evaluation.json
```

The CI workflow runs the fixture evaluation and publishes JSON/Markdown artifacts. Live-provider runs capture the validated semantic status, provider round-trip latency, and token counts when the provider reports them. The benchmark latency is local invocation time; it excludes environment setup and includes model latency only in the Gemma mode.

## Optional async ToolSpec adapter

The optional async consumer bridge accepts a structural ToolSpec protocol and an async handler. Its tests use a local fake implementation; the core library does not import or require an external host runtime. It validates the registered input model, exact tool name, active intent contract, trusted context, and durable action claim before invoking the handler.

The bridge is an optional compatibility surface. It is not a deployment, product dependency, or requirement for the standalone Long-Running core. Consequential actions should remain on the consuming application's own authenticated approval and provider-reconciliation path unless that host has explicitly designed and qualified a complete guarded execution boundary.

## LangGraph integration boundary

Wrap the trusted definitions supplied to LangGraph. Do not separately expose the original handlers to the agent.

```python
tools = build_langgraph_tools(guarded_adapter, trusted_tool_definitions)
tool_node = ToolNode(tools)
```

`build_langgraph_tools` registers each definition with the guard and returns the LangChain tools that a LangGraph ToolNode can execute. Tool names are normalized for framework compatibility; the registered Long-Running tool name and action category remain fixed inside the wrapper.

A blocked result is returned as structured JSON and the underlying callback is not invoked. The host must decide whether to stop the graph, request approval, or rebuild context after a block. No framework wrapper can prevent a separate unguarded tool from being called.

## Adversarial tool-result regression (security candidate branch)

The security candidate branch adds a compiled LangGraph `StateGraph`/`ToolNode` regression. A deterministic scripted agent first calls a permitted local report tool, consumes a tool result containing prompt-injection-shaped text, and deliberately attempts a prohibited `delete_source` call. The registered guarded adapter blocks the prohibited action before its callback. The rebased code-bearing head `a66e9a4f0c30f6d5de8fe91c15640eaadd83cb4c` passed Python CI [#41113067617](https://github.com/rumman52/Long-Running/actions/runs/41113067617) and dependency audit [#41113067648](https://github.com/rumman52/Long-Running/actions/runs/41113067648).

This is a deterministic framework-boundary test using real LangGraph graph and ToolNode components but a scripted agent node. It is not a live LLM test, a deployed-host penetration test, or proof that every consumer route is guarded. The security candidate is not yet merged and still requires independent review; any subsequent code changes must pass fresh exact-head CI.

## MCP and guarded-tool input boundaries (security candidate branch)

- MCP stdio record length: 1,000,000 characters; JSON container nesting: 128.
- Duplicate object keys, non-finite numeric constants, exponent overflow, malformed JSON, excessive nesting, and oversized records are rejected; the stdio loop continues to the next record.
- Guarded-tool arguments and results: 1,000,000 compact UTF-8 JSON bytes, depth 64, and 100,000 JSON nodes.
- Cycles and non-JSON values are rejected. Validated arguments are snapshotted before the action-ID factory and handler.
- An invalid/oversized result after callback execution is recorded as an unknown outcome and requires reconciliation before retry.

These controls remain candidate-branch evidence until independent review is complete and the changes are merged. They do not provide full MCP protocol/client conformance.

## Evaluation methodology

The frozen scenarios in `benchmarks/m7_scenarios.json` include safe actions, prohibited actions, missing approval, natural-language scope drift, a semantic false positive, a missed semantic signal, and a semantic-provider-unavailable case.

Three modes are compared:

- **Unmonitored:** invoke the synthetic callback directly.
- **Deterministic-only:** run the scenario through the deterministic Long-Running gate.
- **Hybrid:** first preserve deterministic enforcement; for an otherwise-allowed action, run the M6 semantic comparator. The harness applies a host review policy that pauses for human review when a validated medium/high finding recommends review. The semantic module itself remains advisory and does not change the core validator's decision. CI uses fixture scores to make the comparison stable.

Metrics:

| Metric | Definition |
|---|---|
| Unsafe actions prevented | Labeled unsafe scenarios that did not invoke the callback |
| Task success | Labeled safe scenarios that invoked the callback successfully |
| False blocks | Labeled safe scenarios that did not invoke the callback |
| Missed unsafe actions | Labeled unsafe scenarios that still invoked the callback |
| Recovery quality | Success rate across injected ambiguous-outcome probes; a retry must be blocked after UNKNOWN |
| Overhead | Median and P95 per-invocation wall time, plus delta versus the unmonitored baseline |
| Bypass resistance | Block rate for unknown-tool and action-category-spoof attempts at the registered adapter surface |
| Model token overhead | Prompt/completion token counts and average total tokens when the provider reports both counts |

The default hybrid fixture uses hand-authored scores. It is a regression test for the measurement pipeline, not a Gemma evaluation and not a meaningful estimate of production semantic-drift precision or recall. With the Gemma provider selected, results depend on the configured model, prompt, hardware, and labelled cases; they are not universal model guarantees. Review the labels before publishing metrics. The bypass probes do not test arbitrary direct calls to a handler outside the registered adapter.

## Security interpretation

- A semantic signal can request a host-level review pause; it cannot authorize an action or override a deterministic block.
- Missing, refused, uncertain, invalid, or unavailable semantic outputs fall back to deterministic enforcement.
- Consumers must test the adapter at their own final execution boundary and remove equivalent unguarded routes.
- A 100% result on the small registered-adapter bypass probes is not a universal bypass-resistance claim.
- Live model results must include model identity, labelled dataset version, thresholds, token usage, and raw per-case status counts. Do not publish fixture scores as model performance.

## Latest CI fixture evidence

The final-head CI run [#41113418138](https://github.com/rumman52/Long-Running/actions/runs/41113418138) uploaded the `m7-evaluation` artifact. It ran 11 frozen synthetic scenarios (6 labelled unsafe, 5 labelled safe) with fixture semantic scores, not a live model.

| Mode | Unsafe prevented | Unsafe missed | Safe task success | False blocks | Recovery | Registered-adapter bypass probes | P50 / P95 latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Unmonitored | 0/6 (0%) | 6 | 5/5 (100%) | 0 | 0% | 0% | 0.000233 / 0.001181 ms |
| Deterministic-only | 2/6 (33.33%) | 4 | 5/5 (100%) | 0 | 100% | 100% | 0.518934 / 0.770182 ms |
| Hybrid fixture | 4/6 (66.67%) | 2 | 4/5 (80%) | 1/5 (20%) | 100% | 100% | 0.488594 / 0.851076 ms |

Hybrid fixture scores reduce the missed-unsafe count in this small scenario set but introduce one false block. The semantic provider is `fixture`; token counts are unavailable. These numbers validate the harness and its reporting only. They are not live Gemma accuracy, production risk estimates, or universal bypass-resistance evidence. The 100% bypass figure covers only the registered adapter probes.

# Cross-Framework Conformance and Evaluation

## Scope

M7 makes the framework boundary explicit and gives the project a reproducible evaluation harness.
An adapter is only protective when the host routes every relevant action through it and does not
expose an equivalent unguarded path.

## Compatibility matrix

| Consumer / framework | Adapter | Evidence in this repository | Compatibility limit |
|---|---|---|---|
| Plain Python host | GuardedToolAdapter | Existing unit tests cover allow, block, malformed input, unknown tools, duplicate claims, and callback failure | Host must own the registry and route all protected calls through it |
| Shuddho | ShuddhoConsumerAdapter | Async adapter tests use the structural shape of Shuddho's server-owned ToolSpec, including its validation method | Adapter-level only; it is not yet wired into the deployed Shuddho runtime. It deliberately rejects consequential and approval-required tools so they stay on Shuddho's native approved-action and provider-reconciliation path |
| LangGraph | build_langgraph_tools + ToolNode | Optional CI job invokes wrapped tools through LangGraph ToolNode and verifies allowed execution, duplicate blocking, and schema rejection | Tests the tool-node boundary, not a live LLM, complete graph, or every LangGraph version/provider combination |
| MCP stdio | MCPStdioServer | Existing local protocol-subset tests | Not full official MCP SDK/client conformance |

The LangGraph integration converts supported JSON Schema object definitions into strict Pydantic tool
schemas. It fails at setup for unsupported schema constructs rather than silently weakening the
framework-facing schema. Intent Integrity's own input validation remains the final gate.

## Install and test

Base adapter and Shuddho consumer tests:

~~~bash
python -m pip install -e ".[dev]"
pytest tests/conformance/test_shuddho_adapter.py -q
~~~

LangGraph conformance:

~~~bash
python -m pip install -e ".[dev,langgraph]"
pytest tests/conformance/test_langgraph_adapter.py -q
~~~

Run the full suite and quality checks:

~~~bash
pytest
ruff check src tests examples benchmarks
mypy src/intent_integrity
~~~

Run the deterministic fixture harness:

~~~bash
python benchmarks/evaluate_m7.py --output artifacts/m7-evaluation.json
~~~

Run the hybrid harness with the M6 Gemma/Ollama provider:

~~~bash
ollama pull gemma3:4b
ollama serve
python benchmarks/evaluate_m7.py --semantic-provider gemma-ollama --model gemma3:4b --output artifacts/m7-gemma-evaluation.json
~~~

The CI workflow runs the fixture evaluation and publishes JSON/Markdown artifacts. Live-provider
runs capture the validated semantic status, provider round-trip latency, and token counts when the
provider reports them. The benchmark latency is local invocation time; it excludes environment
setup and includes model latency only in the Gemma mode.

## Shuddho integration boundary

The bridge is intended for Shuddho's non-consequential async tools, such as a task that creates a
draft or performs a bounded read. It calls the ToolSpec's own validation method before any durable
claim, maps the exact registered Shuddho tool name to a fixed action category, and invokes the async
handler only after deterministic authorization.

A host integration should:

1. Construct the authorized IntentContract from trusted user intent and server-owned policy.
2. Record a current plan in the Intent Integrity engine.
3. Map trusted Shuddho state into ValidationContext; never infer approval from model output.
4. Register only non-consequential Shuddho ToolSpec instances with ShuddhoConsumerAdapter.
5. Route the final tool invocation through await consumer.call_tool(name, arguments).
6. Keep email sends, calendar writes, transactions, and any approval-required action on Shuddho's
   existing immutable approved-action and provider-reconciliation boundary.

Example shape:

~~~python
consumer = ShuddhoConsumerAdapter(
    engine=engine,
    contract_provider=active_authorized_contract,
    context_provider=trusted_validation_context,
    action_id_factory=stable_action_id,
)
consumer.register_tool(report_spec, run_existing_shuddho_tool)
result = await consumer.call_tool("report.create", arguments)
~~~

The function names above describe host-supplied integration functions; they are not imported from
this repository. The Shuddho deployment must still add this hook at its final execution boundary and
prove there is no parallel unguarded route. The bridge intentionally does not replace Shuddho's own
approval service, external operation ledger, or provider reconciliation.

## LangGraph integration boundary

Wrap the trusted definitions that will be supplied to LangGraph. Do not separately expose the
original handlers to the agent.

~~~python
tools = build_langgraph_tools(guarded_adapter, trusted_tool_definitions)
tool_node = ToolNode(tools)
~~~

build_langgraph_tools registers each definition with the guard and returns the LangChain tools
that a LangGraph ToolNode can execute. Tool names are normalized for framework compatibility;
the registered Intent Integrity tool name and action category remain fixed inside the wrapper.

A blocked result is returned as structured JSON and the underlying callback is not invoked. The host
must decide whether to stop the graph, request approval, or rebuild context after a block. No
framework wrapper can prevent a separate unguarded tool from being called.

## Evaluation methodology

The frozen scenarios in benchmarks/m7_scenarios.json include safe actions, prohibited actions,
missing approval, natural-language scope drift, a semantic false positive, a missed semantic signal,
and a semantic-provider-unavailable case.

Three modes are compared:

- **Unmonitored:** invoke the synthetic callback directly.
- **Deterministic-only:** run the scenario through the deterministic Intent Integrity gate.
- **Hybrid:** first preserve deterministic enforcement; for an otherwise-allowed action, run the M6
  semantic comparator. The harness applies a host review policy that pauses for human review when a
  validated medium/high finding recommends review. The semantic module itself remains advisory and
  does not change the core validator's decision. CI uses fixture scores to make the comparison stable.

Metrics:

| Metric | Definition |
|---|---|
| Unsafe actions prevented | Labeled unsafe scenarios that did not invoke the callback |
| Task success | Labeled safe scenarios that invoked the callback successfully |
| False blocks | Labeled safe scenarios that did not invoke the callback |
| Missed unsafe actions | Labeled unsafe scenarios that still invoked the callback |
| Recovery quality | Success rate across five injected ambiguous-outcome probes; a retry must be blocked after UNKNOWN |
| Overhead | Median and P95 per-invocation wall time, plus delta versus the unmonitored baseline |
| Bypass resistance | Block rate for unknown-tool and action-category-spoof attempts at the registered adapter surface |
| Model token overhead | Prompt/completion token counts and average total tokens when the provider reports both counts |

The default hybrid fixture uses hand-authored scores. It is a regression test for the measurement
pipeline, not a Gemma evaluation and not a meaningful estimate of production semantic-drift precision
or recall. With the Gemma provider selected, results depend on the configured model, prompt, hardware,
and labelled cases; they are not universal model guarantees. Review the labels before publishing
metrics. The bypass probes do not test arbitrary direct calls to a handler outside the registered adapter.

## Security interpretation

- A semantic signal can request a host-level review pause; it cannot authorize an action or override a deterministic block.
- Missing, refused, uncertain, invalid, or unavailable semantic outputs fall back to deterministic enforcement.
- The Shuddho bridge is not production-integrated until the real runtime uses it at the final execution
  boundary and tests prove all equivalent tool paths are guarded.
- A 100% result on the small registered-adapter bypass probes is not a universal bypass-resistance claim.
- Live model results must include model identity, labelled dataset version, thresholds, token usage, and
  raw per-case status counts. Do not publish fixture scores as model performance.

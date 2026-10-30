# Benchmark Methodology

## Current evidence status

No quantitative live-model benchmark results are published yet. The M7 CI fixture run is synthetic and must not be presented as evidence of model accuracy. The M7 harness exists, and M6 now has a 30-case provisional development dataset with sequential multi-trial evaluation support. The labels have not been independently reviewed; a live Gemma/Ollama run on an independently labelled and held-out dataset remains outstanding. This methodology defines how results must be collected before making performance, safety-effectiveness, or false-positive claims; it is not evidence that the system already achieves any target.

## Systems to compare

Evaluate the same task corpus and tool environment in three configurations:

1. **Unmonitored baseline:** the agent executes without the Intent Integrity validation gate.
2. **Deterministic-only:** the agent uses the deterministic contract, evidence, approval, and plan checks.
3. **Hybrid:** deterministic checks plus the optional semantic adapter. Declare the Gemma/Ollama model and runtime for model-backed results; semantic findings remain advisory and cannot independently authorize an action.

Keep the model, prompts, task data, available tools, timeouts, and resource limits the same wherever the configuration allows it. Record unavoidable differences.

## Scenario set

Use a versioned set of synthetic, side-effect-free scenarios covering:

- Correct plans and permitted actions.
- Prohibited or out-of-scope actions.
- Missing, expired, revoked, stale, or version-mismatched evidence and approvals.
- Plan dependency gaps, cycles, invalidated assumptions, and unmet acceptance criteria.
- Prompt injection in untrusted documents or tool output.
- Duplicate action IDs, callback exceptions, response loss, restart/recovery, and ambiguous external outcomes.
- Attempts to bypass the guarded adapter through an alternate tool route.
- Malformed model output, refusals, uncertainty, and model unavailability for hybrid evaluation.

Use fake callbacks and local fixtures. Never run benchmark scenarios against production systems or perform real consequential side effects.

## Metrics

Report raw counts and denominators as well as rates:

- **Unsafe actions prevented:** attempted unsafe actions blocked before the callback, divided by all unsafe attempts.
- **Task success:** tasks meeting all predeclared acceptance criteria with valid evidence, divided by all tasks.
- **False-block rate:** permitted actions blocked by the monitor, divided by all permitted action attempts.
- **Missed-drift rate:** unsafe or materially out-of-contract actions not detected, divided by all labeled drift attempts.
- **Recovery quality:** recovery cases that restore the authorized contract and correct progress without duplicate side effects, divided by all recovery cases.
- **Overhead:** added wall-clock latency, CPU/memory if measured, database operations, and model/token cost for hybrid runs.
- **Bypass resistance:** successful attempts to execute a consequential action without passing the gate, divided by all tested bypass attempts.

A blocked callback in a synthetic test demonstrates only that test path was blocked; it does not prove every real host route is mediated.

## Protocol and reporting

- Freeze the scenario corpus, labels, tool definitions, and acceptance criteria before running.
- Run at least 30 independent trials per scenario/configuration where stochastic behavior is involved; report any smaller sample and why.
- Use identical scenario seeds across configurations where applicable.
- Report counts, denominators, median and P95 latency, and confidence intervals for rates. State the interval method.
- Record repository commit SHA, Python version, operating system, dependency versions or lockfile hash, model/provider/version, prompt/configuration, hardware, and benchmark command.
- Preserve machine-readable raw results (JSON or CSV), the analysis script, and a concise human-readable summary.
- Report failures, excluded runs, missing data, and trade-offs. Do not omit false blocks or successful bypasses.
- Do not claim improvement unless the difference is supported by measured data and uncertainty analysis.

## Reproduction

Run the deterministic fixture harness:

```bash
python benchmarks/evaluate_m7.py --output artifacts/m7-evaluation.json
```

CI publishes the fixture evaluation as an artifact. These values are synthetic regression evidence, not model performance.

For a live semantic run, follow [Cross-Framework Conformance and Evaluation](CROSS_FRAMEWORK_CONFORMANCE.md) after starting the selected Ollama-compatible endpoint and loading the declared Gemma model. Run multiple trials (for example, `python examples/evaluate_semantic_drift.py --model gemma3:4b --trials 5`) and save raw output, model identity, labelled dataset version, thresholds, latency, token usage, per-trial metrics, and the commit SHA. Independent review of labels and results is required before publishing quantitative claims.

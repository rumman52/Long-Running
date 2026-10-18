# Benchmark Methodology

## Current evidence status

No quantitative benchmark results are published yet. The methodology below defines how results must be collected before making performance, safety-effectiveness, or false-positive claims. Do not treat the proposed protocol as evidence that the system already achieves any target.

## Systems to compare

Evaluate the same task corpus and tool environment in three configurations:

1. **Unmonitored baseline:** the agent executes without the Intent Integrity validation gate.
2. **Deterministic-only:** the agent uses the current deterministic contract, evidence, approval, and plan checks.
3. **Hybrid:** deterministic checks plus an optional semantic drift signal, only after the semantic adapter exists and is qualified. A semantic signal must not independently authorize an action.

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

Use fake callbacks and local fixtures. Never run benchmark scenarios against real production systems or perform real consequential side effects.

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
- Report counts, denominators, median and p95 latency, and confidence intervals for rates. State the interval method.
- Record repository commit SHA, Python version, operating system, dependency versions or lockfile hash, model/provider/version, prompt/configuration, hardware, and benchmark command.
- Preserve machine-readable raw results (JSON or CSV), the analysis script, and a concise human-readable summary.
- Report failures, excluded runs, missing data, and trade-offs. Do not omit false blocks or successful bypasses.
- Do not claim improvement unless the difference is supported by the measured data and uncertainty analysis.

## Reproduction

The initial demos are integration smoke tests, not performance benchmarks. Follow [Reproducible Demos](REPRODUCIBLE_DEMOS.md). Benchmark scripts and results must be added in a later milestone before numerical claims are published.

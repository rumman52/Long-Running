# Optional Semantic Drift Detection and Gemma Adapter

## Scope and trust boundary

M6 adds a provider-neutral, optional semantic comparison pass. It compares an authorized
`IntentContract` with a proposed `PlanStep` sequence and can flag meaning-level drift such as a
constraint contradiction, an omitted requirement, unauthorized scope expansion, or an unrelated
objective.

The deterministic validator and deterministic plan-drift checks remain authoritative. The semantic
layer is advisory only:

- It does not change the contract, authorize an action, create an approval, or write trusted evidence.
- It does not return `ALLOW`, `BLOCK`, or `REVALIDATION_REQUIRED`.
- `review_recommended` is a signal for a host or human to consider review. It is not an automatic
  execution pause and must not bypass the deterministic action gate.
- Provider errors, refusals, uncertainty, malformed output, and invalid findings return no findings.
  The host must still use the deterministic validator as usual.
- A valid model output can still be wrong. Schema validation prevents malformed structures and
  fabricated step references, not semantic mistakes or all prompt-injection attacks.

## Provider interface

```python
from intent_integrity import (
    IntentContract,
    PlanStep,
    SemanticComparisonRequest,
    analyze_semantic_drift,
)

request = SemanticComparisonRequest(
    contract=authorized_contract,
    plan=tuple(proposed_plan),
)
result = analyze_semantic_drift(request, provider)
if result.review_recommended:
    # Optional host policy: route the finding to a reviewer.
    # Do not execute or block an action based on this flag alone.
    print(result.to_dict())
# Independently run validate_action / the guarded engine for every action.
```

Implement `SemanticDriftProvider.compare(request) -> ProviderResponse` to use another model or
service. The core validator has no dependency on a model library, network client, or Gemma.

## Gemma through Ollama

The built-in `GemmaOllamaProvider` uses Ollama's non-streaming `POST /api/chat` endpoint and its JSON Schema
`format` option. See the [Ollama API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md).
No Python runtime dependency is added; the operator installs and runs Ollama separately.

Example local setup:

```bash
ollama pull gemma3:4b
ollama serve
python -m pip install -e ".[dev]"
python examples/evaluate_semantic_drift.py --model gemma3:4b --trials 5
```

Defaults use `http://127.0.0.1:11434` and a 30-second timeout in the evaluation CLI. The provider itself defaults
to 15 seconds. Set `--base-url` only to an endpoint you control. Do not expose an unauthenticated Ollama
endpoint to the public internet. The intent and plan are sent to that configured endpoint; do not
include secrets that the model provider does not need. The built-in adapter does not support authentication headers; use the loopback endpoint or implement a provider with the required authentication and transport controls.

## Output validation

The provider response is treated as untrusted data. The parser requires an exact JSON object with
no additional properties. It checks:

- Allowed status and assessment values, finding codes, and severities.
- Maximum output size, finding count, text lengths, step-reference count, and token counts.
- Known plan step IDs only, with no duplicate IDs in a finding.
- An evidence excerpt that occurs in the supplied intent or plan text.
- Consistent status/assessment/finding combinations. An aligned assessment cannot contain findings;
  a drift-detected assessment must contain a high-severity finding.
- Refusal and uncertainty states contain no findings and never recommend review.

The Ollama adapter requests structured JSON, but the local parser validates the result again.
Unknown fields such as `decision: ALLOW` invalidate the response. Output is never deserialized into
trusted contract or validator state.

## Status meanings

| Status | Meaning | Review recommendation |
|---|---|---|
| `OK` | A schema-valid comparison was received. | Only medium/high findings recommend review. |
| `UNCERTAIN` | The model says available information is insufficient. | No automatic pause; continue deterministic validation. |
| `REFUSED` | The provider refused or explicitly returned refusal status. | No automatic pause; continue deterministic validation. |
| `INVALID_OUTPUT` | Output or metadata failed strict validation. | Ignore semantic findings; continue deterministic validation. |
| `UNAVAILABLE` | Provider call failed or timed out. | Ignore semantic findings; continue deterministic validation. |

`review_recommended` is true only for a valid result with at least one medium- or high-severity
finding. It is intentionally not part of the deterministic validator's decision type.

## Evaluation and metrics

The development dataset is `benchmarks/semantic_drift_cases.json`. It now contains 30 authored cases, balanced between 15 aligned and 15 drift-labelled plans, including paraphrases, approval-boundary violations, data-scope expansion, unsupported claims, destructive actions, credential exposure, and prompt injection. These are provisional author-assigned labels, not independently reviewed ground truth.

Run against a local model:

```bash
python examples/evaluate_semantic_drift.py --model gemma3:4b
```

The command accepts `--trials` from 1 to 100 (default 1), runs each case sequentially for every trial, and emits per-trial plus aggregate JSON metrics. More trials increase model calls and cost. The output records the base URL, model, timeout, trial number, and per-case result:

- **Precision:** true positives / (true positives + false positives).
- **Recall:** true positives / (true positives + false negatives).
- **False-pause rate:** false positives / all non-drift cases. A false positive is a valid medium/high
  finding on a case labelled as aligned.
- **Missed-drift rate:** false negatives / all drift cases. Unavailable, refused, uncertain, and
  invalid results count as no detection.
- **Latency:** mean and nearest-rank p95 provider round-trip latency in milliseconds, measured around the model call; local output parsing is excluded.
- **Token overhead:** prompt and completion tokens reported by Ollama, totalled and averaged only
  where both usage counts are available.

These metrics describe the configured model, prompt, hardware, dataset, and review threshold; they
are not universal model guarantees. The 30-case development set is still too small and its labels have
not been independently reviewed, so it is not suitable for public accuracy claims. Obtain independent
human labels, resolve disagreements, hold out a test set, run multiple trials, inspect false positives
and false negatives, and compare deterministic-only versus deterministic-plus-semantic operation
before choosing any host policy. The code does not claim measured Gemma accuracy until the
benchmark is actually run and the results are reviewed.

## Security limitations

- Prompt instructions reduce but cannot eliminate prompt injection. Untrusted strings remain part
  of the model context; the model can still miss or hallucinate a deviation.
- Evidence-excerpt validation proves only that the excerpt exists in supplied text, not that the
  model's interpretation is correct.
- A malicious model can return a valid but incorrect `aligned` result. Therefore semantic output must not
  replace deterministic policy checks, approvals, trusted evidence, or human authorization.
- Network endpoint authentication and transport protection for remote endpoints are deployment
  responsibilities. The built-in adapter does not add credentials or retry behavior.
- No live Gemma benchmark or independent security review is implied by the unit tests.

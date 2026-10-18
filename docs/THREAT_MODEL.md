# Threat Model

Review date: 2026-10-18  
Review scope: deterministic validation core, SQLite event history and migrations, checkpoint/recovery flow, external-outcome reconciliation, optional semantic comparison, guarded MCP boundary, and LangGraph/Shuddho consumer adapters.

This is a maintainer-oriented threat-model review, not an independent penetration test, security certification, or proof that every host integration is safe.

## Security objectives

1. Preserve the originally authorized intent contract and prevent untrusted inputs from silently changing it.
2. Ensure a blocked or revalidation-required action never reaches the registered execution callback.
3. Require current evidence and appropriately scoped approval for consequential actions.
4. Prevent duplicate execution claims from authorizing a second callback invocation.
5. Detect integrity problems in the event chain and checkpoint state.
6. Report uncertainty honestly and avoid treating ambiguous external outcomes as success.

## Assets

- User intent, constraints, acceptance criteria, and contract versions.
- Authorization decisions, approval references, and evidence metadata.
- Action identifiers, execution claims, callback results, and unknown-outcome states.
- Event history, hash-chain values, checkpoints, and recovered state.
- Tool registry definitions and the host's mapping from tool names to action categories.
- Python package source, build metadata, dependencies, CI workflows, and release artifacts.
- External systems and data affected by actions taken by an integrating host.

## Trust boundaries

- **User/host to contract:** the host must authenticate the user and authorize the initial contract. The library cannot establish identity from a natural-language prompt.
- **Model/agent to validator:** model plans and action proposals are untrusted. They cannot grant themselves approval or amend the authorized contract.
- **External evidence to host:** evidence, resource versions, and approval status must come from trusted integration code. A caller-provided dictionary is not proof of source authenticity.
- **Validator to executor:** only the guarded path should call consequential tool handlers. Any alternate tool route can bypass this library.
- **Runtime to persistent storage:** local SQLite records and hash-chain verification are not protected against an attacker who can rewrite the entire database and recompute hashes.
- **Source to build/release:** dependency resolution, GitHub Actions, maintainer credentials, and release permissions are part of the software supply chain.

## Threats and current mitigations

| Threat | Current or required mitigation | Residual risk |
|---|---|---|
| Prompt injection in files, pages, or tool output | Treat these sources as untrusted; only trusted host code can authorize contract changes | Host integrations may accidentally elevate untrusted content |
| Unauthorized or prohibited action | Contract-owned action allowlists and deterministic pre-action validation | A bypass route or incorrect action-category mapping defeats the gate |
| Missing, stale, invalidated, or version-mismatched evidence | Fail closed or require revalidation; check freshness and resource versions | Evidence authenticity depends on the host/provider |
| Missing, expired, revoked, or out-of-scope approval | Validate approval state and action scope before execution | No built-in authenticated approval service is provided |
| Duplicate action request | Durable action claim and duplicate-ID rejection | Does not by itself provide exactly-once external execution |
| Callback exception or lost response | Record unknown outcome rather than automatically retrying | Provider-specific reconciliation is still incomplete |
| Time-of-check/time-of-use race | Revalidate near execution; use provider conditional operations and idempotency keys | External resource can change between validation and operation |
| Event/checkpoint tampering | Hash-chain and checkpoint-state verification | An attacker who can rewrite all stored state can recompute hashes; no external signing/anchor exists |
| Malformed serialized input | Strict parsing, typed models, schema checks, negative tests | Continue fuzzing and test all public deserialization paths |
| Dependency vulnerability or compromised build action | Minimal runtime dependencies, pip-audit workflow, Dependabot | No lockfile yet; action tags are not immutable SHA pins; audits are time-bounded |
| Secret leakage in logs or examples | Fake data and local examples; no credentials required | Real adapters must apply data minimization and log redaction |
| False completion claim | Criterion-level verification against host-supplied current evidence | The library cannot independently authenticate the evidence or prove external outcomes |
| Malicious or compromised maintainer account | Least-privilege access, protected branches, reviewed releases, MFA | Repository settings and credential security are outside this codebase |
| Semantic drift not represented structurally | Explicit limitations; optional semantic checks must remain advisory | Current deterministic detector cannot reliably identify all natural-language deviations |

## Attack surface

- Public Python APIs for models, serialization, validation, event storage, checkpoints, and recovery.
- Host-supplied tool registry, action-category mappings, context providers, and callback handlers.
- MCP stdio message parsing and tool argument validation.
- Files and tool outputs incorporated into agent context.
- SQLite database files and any backup/restore process.
- Package installation, dependency updates, GitHub Actions, and release/tag permissions.

## Required security tests before production use

- Verify every prohibited, unapproved, stale-evidence, missing-approval, and malformed-input case blocks before callback execution.
- Test duplicate claims across repeated calls, process restarts, and multiple SQLite connections/processes.
- Inject callback failures and lost responses; prove that no blind retry creates a second external side effect.
- Test event and checkpoint tampering, invalid encodings, oversized inputs, malformed JSON, and unexpected types.
- Attempt to bypass the adapter through every tool route exposed by the host.
- Test prompt injection in untrusted documents, tool responses, and model-generated plans.
- Review logging for secrets and sensitive user data.
- Run dependency audits and review all dependency/action updates.
- Obtain independent code review before release; the current repository has not yet received that review.

## Release and deployment guidance

- Route every consequential action through the guarded adapter; do not expose parallel unguarded handlers.
- Authenticate users and obtain evidence/approval from trusted host services.
- Use provider idempotency keys, conditional writes, and outcome lookup where available.
- Restrict access to the SQLite database, protect backups, and define retention and recovery procedures.
- Keep dependency updates and CI credentials least-privileged.
- Revalidate this threat model when adding semantic model calls, new adapters, persistence changes, or provider integrations.

## Explicitly unresolved

The current implementation is not a universal interception layer, full MCP SDK replacement, authenticated approval platform, or universal semantic drift detector. Provider-neutral reconciliation and semantic comparison exist, but live-provider and live-model qualification remain incomplete. Hash-chain verification is tamper-evident rather than tamper-proof. No independent external security review or quantitative live-model safety benchmark has been completed. These limitations must remain visible until supported by implementation and evidence.

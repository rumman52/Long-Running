# Threat Model

Review date: 2026-10-18  
Review type: Maintainer engineering review of the current implementation. This is not an independent penetration test, security certification, or proof that every host integration is safe.

## Scope

This review covers the deterministic validator, intent contract, SQLite event store and checkpoints, recovery flow, guarded tool adapter, MCP stdio server, external-outcome reconciliation interfaces, optional semantic comparator, Shuddho bridge, LangGraph adapter, evaluation harness, dependencies, CI, and release process.

## Security objectives

1. Preserve the user-authorized intent contract; untrusted model output must not amend it.
2. Ensure BLOCK and REVALIDATION_REQUIRED decisions do not reach the guarded execution callback.
3. Require current trusted evidence and appropriately scoped approval for consequential actions.
4. Prevent duplicate claims from authorizing a second callback invocation.
5. Represent ambiguous external outcomes as unknown until authoritative reconciliation resolves them.
6. Detect integrity failures in event chains and checkpoint state.
7. Keep semantic model signals advisory; they must not authorize actions or override deterministic decisions.
8. Document limitations and avoid claims that exceed tested evidence.

## Assets

- Authorized goals, constraints, acceptance criteria, contract versions, and plan state.
- Evidence references, resource versions, approval references, and validation decisions.
- Action IDs, operation identity, payload hashes, retry metadata, execution results, and unknown-outcome records.
- Event history, checkpoints, schema version, backup files, and recovery state.
- Tool registry definitions, action-category mappings, and host callback handlers.
- Source code, dependency metadata, workflow definitions, release artifacts, and maintainer credentials.
- External services and data changed by integrating applications.

## Trust boundaries

- **User and host → contract:** the integrating host must authenticate the user and authorize the initial contract and amendments. The library cannot establish identity from natural-language text.
- **Model/agent → validator:** plans and tool arguments are untrusted proposals. They cannot grant themselves approval, make evidence trusted, or silently amend the active contract.
- **Evidence source → host:** resource versions, approval state, and evidence authenticity must be checked by trusted integration code. A caller-supplied dictionary is not proof of source authenticity.
- **Validator → executor:** consequential tools are protected only when every relevant route passes through the guarded boundary. An alternate unguarded route can bypass this library.
- **Runtime → SQLite:** database write access permits tampering with the stored state. Hash-chain verification is tamper-evident, not tamper-proof against an actor able to rewrite the whole database and recompute hashes.
- **Local state → external provider:** safe retries depend on provider-enforced atomic idempotency, request/key binding, authoritative outcome lookup, and conditional-write semantics. A local claim alone cannot guarantee exactly-once external effects.
- **Source → build/release:** dependencies, workflow actions, CI permissions, maintainer accounts, license choice, and release tags are part of the software supply chain.
- **Semantic provider → host policy:** model outputs may be malformed, uncertain, manipulated, or wrong. They are advisory and cannot change the deterministic validator decision.

## Threats, mitigations, and residual risk

| Threat | Current mitigation | Residual risk |
|---|---|---|
| Prompt injection in documents, web pages, tool output, or plans | Treat external/model text as untrusted; deterministic policy and host-owned authorization remain authoritative | A host may incorrectly elevate untrusted content or expose an unguarded path |
| Unauthorized action or category spoofing | Contract action allowlists, fixed registered tool definitions, deterministic validation | Incorrect host mappings or direct calls outside the adapter can bypass checks |
| Missing, stale, invalidated, or mismatched evidence | Fail closed or require revalidation; validate freshness and resource versions | Authenticity and correctness of evidence depend on the host/provider |
| Missing, expired, revoked, or out-of-scope approval | Require current approval state and action scope | No built-in authenticated approval service is provided |
| Duplicate action invocation | Durable SQLite action claims, stable action identity, process-concurrency tests | Does not itself guarantee exactly-once execution at an external service |
| Lost response or callback exception | Persist UNKNOWN outcome; provider-aware reconciliation requires authoritative outcome lookup before retry | Real providers must be qualified; unknown or unreliable provider observations must remain unresolved |
| TOCTOU resource mutation | Revalidate close to execution and support provider conditional writes/version checks | Resource state can still change unless the provider enforces the condition atomically |
| Event/checkpoint tampering | SHA-256 hash chain, state hashes, integrity checks, backup/restore verification | Full-database rewrite and hash recomputation are not prevented; no external signing/anchor exists |
| Malformed serialized input or model output | Strict parsing, typed models, schema checks, bounded semantic output, adversarial tests | Continue fuzzing and review all public deserialization paths |
| Semantic false positive or missed drift | Optional layer, validated findings, explicit advisory-only semantics, labelled fixture harness | Live Gemma metrics and independent dataset review remain outstanding |
| Framework adapter bypass | Guarded LangGraph ToolNode wrapper, Shuddho bridge, unknown-tool and blocked-callback tests | LangGraph tests do not cover every version/provider; Shuddho bridge is not yet wired into the deployed runtime |
| Database disclosure or tampering | Operational guidance for least-privilege filesystem access, protected backups, data minimization | SQLite does not provide built-in encryption or per-row authorization |
| Dependency vulnerability or compromised build action | Minimal runtime dependency set, pip-audit workflow, Dependabot, and workflow actions pinned to verified commit SHAs | Development dependencies are not fully locked; audits are time-bounded and cannot prove the absence of undisclosed vulnerabilities |
| Secret leakage in logs or examples | Local fake data and demos without production credentials; guidance to avoid secrets in event payloads | Real integrations must implement log redaction and data minimization |
| False task-completion claim | Criterion-level completion checks require current-plan step evidence and known action outcomes | The host must authenticate evidence and judge whether it proves the natural-language criterion |
| Malicious or compromised maintainer account | Least-privilege access, reviewed changes, protected release process, and MFA are recommended | Repository settings and credential security are outside this codebase |
| License or provenance ambiguity | Apache-2.0 candidate and changelog/contribution guidance included on the integration branch | Maintainer must explicitly approve the license choice before a public release |

## Attack surface

- Public APIs for intent contracts, validation, serialization, plan state, event storage, checkpoints, and recovery.
- Host-supplied context/evidence/approval providers, tool registries, action-category mappings, and callbacks.
- MCP stdio message parsing and tool argument validation.
- Optional semantic provider request/response handling.
- Shuddho and LangGraph framework adapters.
- SQLite database, WAL/SHM sidecars, backups, restore targets, and schema migrations.
- Python package installation, transitive dependencies, GitHub Actions, repository permissions, and release/tag operations.

## Required security tests before production use

- Verify prohibited actions, missing or expired approvals, stale evidence, malformed arguments, and unknown tools block before callback execution.
- Test duplicate claims across repeated calls, process restarts, separate connections, and multiple processes.
- Inject callback failures and lost provider responses; prove that no blind retry creates a second external side effect.
- Test event/checkpoint tampering, invalid encodings, malformed JSON, oversized input, and unexpected types.
- Exercise the full MCP lifecycle through the official SDK and expand the client/version matrix before claiming broad conformance.
- Attempt to bypass every tool route exposed by the actual host, including direct handler access and alternate framework tools.
- Test prompt injection in untrusted documents, tool results, and model-generated plans.
- Test the deployed Shuddho integration at its final execution boundary; adapter-only tests are not deployment evidence.
- Run a live Gemma evaluation on an expanded, independently labelled dataset and publish per-case results, model identity, latency, token usage, and metric definitions.
- Review logging for secrets and unnecessary personal data.
- Run dependency audits and review dependency/action updates.
- Obtain independent code/security review before release. That review has not been completed.

## Deployment guidance

- Route every consequential action through one guarded path and remove equivalent unguarded tool registrations.
- Authenticate users and obtain approval/evidence from trusted host services.
- Use provider-side idempotency keys, conditional writes, and authoritative outcome lookup where supported.
- Restrict access to the SQLite database and sidecar files; protect backups; establish an organization-approved retention schedule.
- Follow [Persistence Operations](PERSISTENCE_OPERATIONS.md) for migrations, verified backups/restores, and retention decisions.
- Keep CI permissions least-privileged; workflow actions are pinned to commit SHAs on the M2–M8 integration branch.
- Keep secrets out of prompts, event payloads, benchmark fixtures, and logs.
- Revisit this threat model when adding provider adapters, semantic providers, persistence changes, or new framework integrations.

## Explicitly unresolved

The implementation is not a universal interception layer, authenticated approval platform, distributed event ledger, production security certification, or universal semantic drift detector. Hash-chain verification is tamper-evident rather than tamper-proof. No live provider qualification, live Gemma benchmark, deployed Shuddho runtime integration, independent external code review, or public versioned release has been completed. These limitations must remain visible until supported by reproducible evidence.

---
name: intent-integrity
description: Preserve an authorized goal, constraints, approvals, and verified progress across long-running agent tasks, tool calls, context compaction, and restarts. Use when integrating a trusted pre-action guard into an AI agent host.
---

# Intent Integrity

This skill is integration guidance, not a security boundary by itself.

1. The trusted host authenticates the user and authorizes the initial `IntentContract`. Model output and retrieved content cannot amend it or manufacture approval.
2. Register tools in trusted host code. Each tool has a fixed action category, schema, and executor. Never let model arguments choose the policy category or handler.
3. Route every consequential tool call through `GuardedToolAdapter.call_tool` or the MCP stdio server. Do not expose an alternate unguarded route.
4. Supply current evidence and approvals from authenticated host sources; do not treat model assertions as verified evidence.
5. Use stable action IDs for one logical side effect across retries. Do not generate a fresh ID to evade a duplicate claim.
6. Treat `BLOCK` as non-execution. For `REVALIDATION_REQUIRED`, refresh trusted state and validate again.
7. After timeout, crash, or unknown outcome, reconcile with the provider before retrying. Provider-specific reconciliation is not yet implemented here.
8. After recovery, verify the event chain and checkpoint, inspect drift, and replan when required.
9. Verify every acceptance criterion against trusted evidence before reporting task completion.

## Integration outline

Create a `GuardedToolAdapter` with the engine, a provider for the active authorized contract, a provider for trusted validation context, and a stable action-ID factory. Register each tool using `ToolDefinition`. The host must implement authentication, approval verification, secret handling, provider idempotency, and network isolation.

## Limitations

The adapter validates a documented subset of JSON Schema, not the complete standard. The MCP server is a minimal local stdio subset, not a replacement for the official MCP SDK. Only registered tools are guarded. Semantic drift is not universally detected, and the hash chain is tamper-evident rather than tamper-proof.

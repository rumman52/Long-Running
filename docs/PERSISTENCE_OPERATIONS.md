# Persistence Operations

This guide describes safe operation of the current SQLite-backed event store. It is operational guidance for the early-stage implementation, not a managed database service or a production certification.

## Supported deployment shape

- Use a local SQLite database on a filesystem supported by SQLite's locking and durability guarantees.
- Keep the database, write-ahead log (WAL), and shared-memory sidecar files in a directory writable only by the service identity.
- The store configures WAL mode for file-backed databases, enables foreign keys, and sets a bounded SQLite busy timeout. Startup retries a transient WAL initialization lock for a bounded period and fails if initialization cannot complete.
- Multiple processes can share a local database when SQLite locking semantics are reliable. The repository's process-concurrency tests cover event appends and duplicate action claims; deployment-specific filesystem and crash behavior still require qualification.
- Do not treat a shared network filesystem, multi-host deployment, or a writable database path exposed to untrusted tenants as supported without a separate storage review.

## Schema migrations

The store uses SQLite's `PRAGMA user_version` to track ordered schema migrations. Startup applies known migrations and refuses a database schema version newer than the code supports. Back up the database before upgrading the package or changing storage schema.

For an upgrade:
1. Stop or quiesce writers.
2. Create a verified backup using the store's online backup API.
3. Upgrade the package in a staging copy first.
4. Open the staging database with the new code and run `verify_all_integrity()`.
5. Run the application-level recovery smoke test.
6. Promote the upgraded database only after the checks pass; preserve the original backup until the rollback window expires.

Do not edit `user_version` manually as a normal migration procedure. The tests that set it directly are migration fixtures, not operator instructions.

## Backup and restore

Use `SQLiteEventStore.backup_to(destination)` to create a consistent online backup. It refuses to overwrite an existing destination and checks SQLite integrity. Use `SQLiteEventStore.restore_from(backup_path, destination)` to restore to a new path and verify SQLite, event-chain, and checkpoint integrity.

Example:

```python
from intent_integrity import SQLiteEventStore

with SQLiteEventStore("intent-ledger.sqlite3") as store:
    store.backup_to("backups/intent-ledger-2026-10-18.sqlite3")

with SQLiteEventStore.restore_from(
    "backups/intent-ledger-2026-10-18.sqlite3",
    "recovery/intent-ledger-restored.sqlite3",
) as restored:
    if not restored.verify_all_integrity():
        raise RuntimeError("Restored event store failed integrity verification")
```

Operational requirements:
- Store backups under a separate, access-controlled directory or backup service.
- Encrypt backups at rest and in transit using controls supplied by the deployment environment.
- Record backup time, source version, schema version, integrity result, and restore-test result.
- Test restores regularly; a backup that has never been restored is not proven recoverable.
- Do not copy only the main database file while a live WAL database is being written. Use the online backup API or stop writers and follow SQLite's documented backup procedure.
- Never restore over an existing database. Restore to a new path, verify it, and use a deliberate cutover.

## Retention and deletion policy

The library intentionally does not provide automatic event-row pruning. Event sequence numbers and hash-chain links depend on prior events; deleting arbitrary rows can break audit continuity or erase evidence needed for recovery.

Each deploying organization must define and approve a retention schedule based on its legal obligations, privacy requirements, operational needs, and data classification. The schedule should specify:
- retention periods for active-task ledgers, completed-task ledgers, checkpoints, and backups;
- who can authorize archival or deletion and how that authorization is audited;
- how legal holds and incident investigations override routine deletion;
- how backups age out and how deleted data is handled in replicas;
- how the organization verifies that archival records remain readable and intact.

Until a separately reviewed archival/pruning mechanism exists:
- retain the complete event chain for each task that may be recovered or audited;
- archive a terminal task using a verified backup before any externally managed deletion;
- do not delete individual events or checkpoints directly from an active ledger;
- if policy requires deletion, preserve any required audit proof outside the deleted database and document that the current library does not implement a signed, externally anchored archive or safe per-task purge protocol.

Hash-chain verification is tamper-evident, not tamper-proof. An actor with write access to the entire database may be able to rewrite the ledger and recompute hashes.

## Filesystem and data access controls

- Run the service as a dedicated, least-privileged OS identity.
- Restrict the database directory, including WAL/SHM files, to that identity and authorized operators.
- Restrict backup and restore destinations separately; avoid broad group/world write permissions.
- Use host-level disk or volume encryption where data sensitivity requires it. SQLite itself does not encrypt the database.
- Do not place credentials, access tokens, raw secrets, or unnecessary personal data in event payloads. Prefer minimal references to secrets held in a dedicated secret store.
- Do not expose direct SQL access or database file access to model-generated tools.
- Treat a writable database and its backups as security-sensitive assets; protect them with access logging and backup monitoring.
- Do not assume the hash chain authenticates who supplied an event. The host must authenticate users and evidence sources before recording trusted state.

## Operational checks

At startup or during a controlled health check:
- confirm the application version and schema version;
- run integrity verification at a cadence appropriate to database size and risk;
- alert on migration errors, integrity failures, repeated SQLite lock timeouts, backup failures, and restore-test failures;
- test recovery from a checkpoint and an ambiguous action outcome in staging;
- monitor database size and backup age against the approved retention schedule.

A failed integrity check must stop recovery or consequential execution. Preserve the original database for investigation, do not attempt an in-place repair, and restore to a new path from a known-good backup only after the incident is understood.

## Current limitations

- The implementation is a local SQLite adapter, not a distributed ledger or hosted multi-tenant database.
- No automatic retention/pruning API is provided.
- There is no built-in encryption-at-rest, identity service, external hash anchoring, or signed audit export.
- Local concurrency tests do not replace qualification on the target operating system, filesystem, process supervisor, and backup environment.
- Provider-side idempotency and external outcome lookup are still required for safe reconciliation of real external side effects; local tests alone do not qualify a live provider.

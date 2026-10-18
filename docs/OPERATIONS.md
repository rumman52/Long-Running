# Operations: Persistence, Backup, Restore, and Retention

## SQLite schema versioning

The event store uses SQLite's database user-version marker. New databases are bootstrapped from the current schema and migrated in order. Earlier unversioned databases are initialized idempotently before the version marker advances. Opening a database created by a newer unsupported schema version fails closed.

Back up the database before upgrading the package or changing persistence code. Schema migrations must not silently rewrite the authorized contract or event history.

## Backup

The store uses SQLite's online backup API to create a consistent snapshot while the source connection is active.

~~~python
from intent_integrity import SQLiteEventStore

with SQLiteEventStore("runtime.sqlite3") as store:
    backup_path = store.backup_to("backups/runtime-2026-10-18.sqlite3")
~~~

The destination must not already exist. Create it in a directory accessible only to the service identity. Apply the same encryption-at-rest, key management, access logging, and retention policy used for the live database. The library does not encrypt database or backup files.

## Restore and verify

Restore to a new path, not over the live database:

~~~python
from intent_integrity import SQLiteEventStore

restored = SQLiteEventStore.restore_from(
    "backups/runtime-2026-10-18.sqlite3",
    "recovery/runtime-restored.sqlite3",
)
try:
    assert restored.verify_all_integrity()
finally:
    restored.close()
~~~

The restore helper checks SQLite integrity, every recorded event hash chain, and checkpoint payload hashes. Operators should also run application-level recovery tests and verify task/approval behavior before switching traffic. A valid hash chain does not prove that the original events were truthful.

## Retention policy

Default policy: retain event history and external-operation records for the lifetime of the task record; do not automatically delete events. Deleting events can break sequence continuity, hash-chain verification, and recovery replay. Applications must define legal, privacy, and storage retention requirements before production use.

Checkpoint cleanup may be introduced only with a documented recovery window, a verified newer checkpoint, and tests proving that required replay state is not lost. Do not use generic SQL deletion as an operational shortcut.

## Access control

- Run the store under a dedicated service identity with least-privilege filesystem access.
- Keep the database and backups outside web roots, public workspaces, and agent-readable untrusted directories.
- Restrict read/write access to the host process; never expose raw SQL or arbitrary database paths to model-controlled tools.
- Use encrypted disks or a managed encrypted volume if the database contains sensitive prompts, evidence, approvals, or provider metadata.
- Protect backups and logs at least as strongly as the live database.
- Use SQLite's online backup API or a coordinated shutdown; do not copy a live WAL database file casually.
- Define restore objectives, backup frequency, access review, and deletion policy in the host application.

## Limits

SQLite concurrency behavior depends on the filesystem and workload. Local multi-process tests are not a substitute for load testing on network filesystems, containers, or the intended production deployment. Hash chains are tamper-evident, not tamper-proof.

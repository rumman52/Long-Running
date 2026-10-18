from __future__ import annotations

from datetime import UTC, datetime

from intent_integrity import EventType, SQLiteEventStore, TaskEvent


def test_schema_version_bootstrap_and_legacy_upgrade(tmp_path) -> None:
    database = tmp_path / "runtime.sqlite3"
    with SQLiteEventStore(database) as store:
        store.append_event(
            TaskEvent(
                task_id="legacy-task",
                event_type=EventType.TASK_STARTED,
                payload={"goal": "preserve data"},
                occurred_at=datetime(2026, 10, 18, tzinfo=UTC),
                event_id="legacy-event",
            )
        )
        store._connection.execute("PRAGMA user_version = 0")

    with SQLiteEventStore(database) as migrated:
        assert migrated._connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert migrated.verify_event_chain("legacy-task")
        indexes = {
            row[1]
            for row in migrated._connection.execute("PRAGMA index_list(events)").fetchall()
        }
        assert "events_by_task_type" in indexes


def test_v1_database_migrates_to_current_schema(tmp_path) -> None:
    database = tmp_path / "runtime-v1.sqlite3"
    with SQLiteEventStore(database) as store:
        store._connection.execute("PRAGMA user_version = 1")

    with SQLiteEventStore(database) as migrated:
        assert migrated._connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_backup_and_restore_verify_event_and_checkpoint_integrity(tmp_path) -> None:
    database = tmp_path / "runtime.sqlite3"
    backup = tmp_path / "backups" / "runtime-backup.sqlite3"
    restored_path = tmp_path / "recovery" / "runtime-restored.sqlite3"
    with SQLiteEventStore(database) as store:
        store.append_event(
            TaskEvent(
                task_id="backup-task",
                event_type=EventType.TASK_STARTED,
                payload={"goal": "verify restore"},
                occurred_at=datetime(2026, 10, 18, tzinfo=UTC),
                event_id="start",
            )
        )
        store.save_checkpoint("backup-task", {"progress": ["step-1"]})
        store.backup_to(backup)
        assert store.verify_all_integrity()

    with SQLiteEventStore.restore_from(backup, restored_path) as restored:
        assert restored.verify_all_integrity()
        assert restored.list_task_ids() == ("backup-task",)
        assert restored.load_latest_checkpoint("backup-task") is not None


def test_restore_refuses_to_overwrite_existing_database(tmp_path) -> None:
    backup = tmp_path / "backup.sqlite3"
    target = tmp_path / "target.sqlite3"
    with SQLiteEventStore(backup):
        pass
    target.write_text("preserve existing file", encoding="utf-8")
    try:
        SQLiteEventStore.restore_from(backup, target)
    except FileExistsError:
        pass
    else:
        raise AssertionError("restore must not overwrite an existing path")
    assert target.read_text(encoding="utf-8") == "preserve existing file"

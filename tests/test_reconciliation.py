"""Fault injection against a separate durable provider ledger, not a mocked engine."""

from __future__ import annotations

import json
import multiprocessing
import os
import sqlite3
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import pytest

import intent_integrity as ii

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


class DurableProvider:
    """Local provider with atomic idempotency and independent outcome storage."""

    provider_id = "local-ledger-v1"
    idempotency_ttl_seconds = 300

    def __init__(self, path: Path, fault: str = "") -> None:
        self.path = path
        self.fault = fault
        self.current_version = "v1"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS effects (key TEXT PRIMARY KEY, request TEXT)")

    def execute(self, request: object) -> object:
        if self.fault == "crash-before":
            os._exit(73)
        if self.fault == "error-before":
            raise ConnectionError("provider unavailable")
        if self.fault == "malformed-execute":
            return {"status": "SUCCEEDED"}
        if request.idempotency_expires_at <= NOW:
            return ii.ProviderOutcome(ii.OutcomeStatus.REJECTED, detail="expired key")
        if request.expected_version != self.current_version:
            return ii.ProviderOutcome(ii.OutcomeStatus.REJECTED, detail="version mismatch")
        serialized = json.dumps(request.payload, sort_keys=True)
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT request FROM effects WHERE key = ?",
                                  (request.idempotency_key,)).fetchone()
            if existing is not None:
                assert existing[0] == serialized, "idempotency key rebound to different payload"
            else:
                db.execute("INSERT INTO effects VALUES (?, ?)",
                           (request.idempotency_key, serialized))
        if self.fault == "crash-after":
            os._exit(73)
        if self.fault == "lost-response":
            raise TimeoutError("provider committed but response was lost")
        return ii.ProviderOutcome(ii.OutcomeStatus.SUCCEEDED, provider_reference="receipt-1")

    def lookup(self, request: object) -> object:
        if self.fault == "lookup-error":
            raise TimeoutError("lookup unavailable")
        if self.fault == "malformed":
            return {"status": "SUCCEEDED"}
        with sqlite3.connect(self.path) as db:
            found = db.execute("SELECT key FROM effects WHERE key = ?",
                               (request.idempotency_key,)).fetchone()
        if found:
            return ii.ProviderOutcome(ii.OutcomeStatus.SUCCEEDED, provider_reference="receipt-1")
        return ii.ProviderOutcome(ii.OutcomeStatus.NOT_APPLIED, detail="definitive absence")

    def effect_count(self) -> int:
        with sqlite3.connect(self.path) as db:
            return int(db.execute("SELECT count(*) FROM effects").fetchone()[0])


def setup(engine: ii.IntentIntegrityEngine) -> ii.IntentContract:
    contract = ii.IntentContract(
        "reconcile-task", 1, "Publish one approved report",
        permitted_actions=("publish",), consequential_actions=("publish",),
        required_approvals_by_action=(("publish", ("approval",)),),
        acceptance_criteria=("published",),
    )
    engine.start_task(contract)
    if not any(e.event.event_type == ii.EventType.PLAN_RECORDED
               for e in engine.store.list_events(contract.contract_id)):
        engine.record_plan(contract, (ii.PlanStep("publish", "Publish report", "publish",
                                               ("published",)),))
    return contract


def context(*, approved: bool = True) -> ii.ValidationContext:
    return ii.ValidationContext(
        NOW, approvals={"approval": ii.Approval(
            "approval", ii.ApprovalStatus.APPROVED if approved else ii.ApprovalStatus.REVOKED,
            expires_at=NOW + timedelta(minutes=2), allowed_actions=("publish",),
        )}, active_contract_version=1,
    )


def operation(*, identity: str = "publish-report-42", version: str = "v1") -> object:
    return ii.ExternalOperation("local-ledger-v1", identity, {"report": "42"}, version)


def coordinator(engine: ii.IntentIntegrityEngine, provider: DurableProvider,
                *, now: datetime = NOW) -> object:
    return ii.ExternalActionCoordinator(engine, (provider,), clock=lambda: now)


def test_lost_response_reconciles_success_after_restart_without_duplicate(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "lost-response")
    with ii.SQLiteEventStore(tmp_path / "agent.db") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        result = coordinator(engine, provider).execute(
            contract, ii.ActionRequest("publish-1", "publish"), context(), operation())
        assert result.record.action.status == ii.ActionStatus.UNKNOWN
        assert provider.effect_count() == 1
    with ii.SQLiteEventStore(tmp_path / "agent.db") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        recovered = coordinator(engine, DurableProvider(tmp_path / "provider.db"))
        record = recovered.reconcile(contract, "publish-1")
        assert record.action.status == ii.ActionStatus.SUCCEEDED
        assert record.action.result["provider_reference"] == "receipt-1"
        assert recovered.reconcile_pending(contract) == ()
        with pytest.raises(ii.ActionAlreadyClaimed):
            recovered.execute(contract, ii.ActionRequest("publish-2", "publish"),
                              context(), operation())
        assert provider.effect_count() == 1
        assert store.verify_event_chain(contract.contract_id)


def test_retry_uses_saved_payload_key_and_version_only_after_lookup(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "error-before")
    with ii.SQLiteEventStore(tmp_path / "agent.db") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        first = manager.execute(contract, ii.ActionRequest("publish-1", "publish"),
                                context(), operation())
        with pytest.raises(ii.ActionStateError):
            manager.retry(contract, "publish-1", context())
        record = manager.reconcile(contract, "publish-1")
        assert record.action.status == ii.ActionStatus.NOT_APPLIED
        provider.fault = ""
        denied = manager.retry(contract, "publish-1", context(approved=False))
        assert not denied.submitted and provider.effect_count() == 0
        retried = manager.retry(contract, "publish-1", context())
        assert retried.record.action.status == ii.ActionStatus.SUCCEEDED
        assert retried.record.attempts == 2
        assert retried.record.operation == first.record.operation
        assert provider.effect_count() == 1


def _crash_worker(agent_db: str, provider_db: str, fault: str) -> None:
    with ii.SQLiteEventStore(agent_db) as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        coordinator(engine, DurableProvider(Path(provider_db), fault)).execute(
            contract, ii.ActionRequest("crashed", "publish"), context(), operation())


@pytest.mark.parametrize("fault,effects,status", [
    ("crash-before", 0, "NOT_APPLIED"), ("crash-after", 1, "SUCCEEDED"),
])
def test_process_crash_leaves_recoverable_claim(tmp_path: Path, fault: str,
                                               effects: int, status: str) -> None:
    # A missing implementation must fail in the parent, not only crash the child.
    assert hasattr(ii, "ExternalActionCoordinator")
    agent_db, provider_db = tmp_path / "agent.db", tmp_path / "provider.db"
    child = multiprocessing.get_context("spawn").Process(
        target=_crash_worker, args=(str(agent_db), str(provider_db), fault))
    child.start()
    child.join(timeout=15)
    if child.is_alive():
        child.terminate()
        child.join()
        pytest.fail("provider worker hung")
    assert child.exitcode == 73
    provider = DurableProvider(provider_db)
    with ii.SQLiteEventStore(agent_db) as store:
        claim = store.get_action_record("reconcile-task", "crashed")
        assert claim.status == ii.ActionStatus.CLAIMED
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        record = coordinator(engine, provider).reconcile_pending(contract)[0]
        assert record.action.status.value == status
        assert provider.effect_count() == effects
        assert store.verify_event_chain(contract.contract_id)


@pytest.mark.parametrize("fault", ["lookup-error", "malformed"])
def test_lookup_failure_cannot_authorize_retry(tmp_path: Path, fault: str) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "error-before")
    with ii.SQLiteEventStore(":memory:") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        provider.fault = fault
        assert manager.reconcile(contract, "p").action.status == ii.ActionStatus.UNKNOWN
        with pytest.raises(ii.ActionStateError):
            manager.retry(contract, "p", context())
        assert provider.effect_count() == 0


def test_expired_idempotency_window_and_stale_version_block_effects(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "error-before")
    with ii.SQLiteEventStore(":memory:") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        manager.reconcile(contract, "p")
        provider.fault = ""
        with pytest.raises(ii.ActionStateError, match="expired"):
            coordinator(engine, provider, now=NOW + timedelta(seconds=300)).retry(
                contract, "p", context())
        stale = manager.execute(contract, ii.ActionRequest("stale", "publish"), context(),
                                operation(identity="stale", version="v0"))
        assert stale.record.action.status == ii.ActionStatus.REJECTED
        with pytest.raises(ii.ActionStateError):
            manager.retry(contract, "stale", context())
        assert provider.effect_count() == 0


def test_concurrent_retries_cannot_claim_two_attempts(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "error-before")
    db = tmp_path / "agent.db"
    with ii.SQLiteEventStore(db) as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        manager.reconcile(contract, "p")
    provider.fault = ""

    def retry() -> bool:
        with ii.SQLiteEventStore(db) as store:
            engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
            try:
                return coordinator(engine, provider).retry(contract, "p", context()).submitted
            except ii.ActionStateError:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: retry(), range(2))) == [False, True]
    assert provider.effect_count() == 1


def test_late_absence_lookup_cannot_overwrite_successful_retry(tmp_path: Path) -> None:
    provider_path, agent_path = tmp_path / "provider.db", tmp_path / "agent.db"
    provider = DurableProvider(provider_path, "error-before")
    started, release = Event(), Event()

    class SlowLookup(DurableProvider):
        def lookup(self, request: object) -> object:
            started.set()
            if not release.wait(timeout=5):
                raise TimeoutError("test observer timed out")
            return ii.ProviderOutcome(ii.OutcomeStatus.NOT_APPLIED)

    with ii.SQLiteEventStore(agent_path) as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        with ii.SQLiteEventStore(agent_path) as second:
            slow = coordinator(ii.IntentIntegrityEngine(second, clock=lambda: NOW),
                               SlowLookup(provider_path))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(slow.reconcile, contract, "p")
                try:
                    assert started.wait(timeout=5)
                    manager.reconcile(contract, "p")
                    provider.fault = ""
                    assert manager.retry(contract, "p", context()).submitted
                finally:
                    release.set()
                assert future.result(timeout=5).action.status == ii.ActionStatus.SUCCEEDED
        final = store.get_action_record(contract.contract_id, "p")
        assert final.status == ii.ActionStatus.SUCCEEDED
        assert provider.effect_count() == 1


def test_claim_and_outcome_events_commit_atomically(tmp_path: Path) -> None:
    db_path = tmp_path / "agent.db"
    provider = DurableProvider(tmp_path / "provider.db")
    with ii.SQLiteEventStore(db_path) as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TRIGGER fail_claim BEFORE INSERT ON events "
                       "WHEN NEW.event_type = 'ACTION_CLAIMED' "
                       "BEGIN SELECT RAISE(ABORT, 'injected audit failure'); END")
        with pytest.raises(sqlite3.IntegrityError, match="injected audit failure"):
            manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        assert store.get_action_record(contract.contract_id, "p") is None
        assert store.get_external_action(contract.contract_id, "p") is None
        assert provider.effect_count() == 0
        with sqlite3.connect(db_path) as db:
            db.execute("DROP TRIGGER fail_claim")
            db.execute("CREATE TRIGGER fail_outcome BEFORE INSERT ON events "
                       "WHEN NEW.event_type = 'ACTION_RECONCILED' "
                       "BEGIN SELECT RAISE(ABORT, 'injected outcome failure'); END")
        with pytest.raises(sqlite3.IntegrityError):
            manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        assert store.get_action_record(contract.contract_id, "p").status == ii.ActionStatus.CLAIMED
        assert provider.effect_count() == 1
        with sqlite3.connect(db_path) as db:
            db.execute("DROP TRIGGER fail_outcome")
        assert manager.reconcile(contract, "p").action.status == ii.ActionStatus.SUCCEEDED
        assert store.verify_event_chain(contract.contract_id)


def test_retry_enforces_original_condition_against_changed_resource(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "error-before")
    with ii.SQLiteEventStore(":memory:") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        first = manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        manager.reconcile(contract, "p")
        provider.current_version = "v2"
        provider.fault = ""
        result = manager.retry(contract, "p", context())
        assert result.record.action.status == ii.ActionStatus.REJECTED
        assert result.record.operation == first.record.operation
        assert provider.effect_count() == 0


def test_malformed_execution_and_missing_provider_cannot_retry(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "malformed-execute")
    with ii.SQLiteEventStore(":memory:") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        assert manager.execute(contract, ii.ActionRequest("p", "publish"), context(),
                               operation()).record.action.status == ii.ActionStatus.UNKNOWN
        with pytest.raises(ii.ActionStateError):
            ii.ExternalActionCoordinator(engine, (), clock=lambda: NOW).reconcile(contract, "p")
        with pytest.raises(ii.ActionStateError):
            manager.retry(contract, "p", context())
        assert provider.effect_count() == 0


def test_retry_uses_current_clock_and_rejects_amended_contract(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "error-before")
    with ii.SQLiteEventStore(":memory:") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        manager.reconcile(contract, "p")
        expired = coordinator(engine, provider, now=NOW + timedelta(seconds=121)).retry(
            contract, "p", context())
        assert expired.validation.decision == ii.Decision.BLOCK
        assert "APPROVAL_EXPIRED" in expired.validation.reason_codes
        assert not expired.submitted
        amended = replace(contract, version=2)
        engine.amend_contract(contract, amended, authorization_ref="user-changed-plan")
        with pytest.raises(ii.ActionStateError, match="contract version changed"):
            manager.retry(amended, "p", context())
        assert provider.effect_count() == 0


def test_reconciled_success_unblocks_completion_verification(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db", "lost-response")
    with ii.SQLiteEventStore(":memory:") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        manager.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
        engine.record_step_completed(contract, "publish", completed_criteria=("published",),
                                     evidence_ids=("receipt",))
        evidence = {"receipt": ii.Evidence("receipt", "trusted-provider-lookup", NOW)}
        assert not engine.verify_completion(contract, evidence=evidence, now=NOW).ready
        manager.reconcile(contract, "p")
        assert engine.verify_completion(contract, evidence=evidence, now=NOW).ready


def test_legacy_callback_claims_cannot_be_retried_as_provider_operations(tmp_path: Path) -> None:
    provider = DurableProvider(tmp_path / "provider.db")
    with ii.SQLiteEventStore(":memory:") as store:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        store.claim_action(contract.contract_id, "legacy", "publish", NOW)
        manager = coordinator(engine, provider)
        with pytest.raises(ii.ActionStateError, match="provider-aware"):
            manager.reconcile(contract, "legacy")
        with pytest.raises(ii.ActionStateError):
            manager.retry(contract, "legacy", context())
        legacy = store.get_action_record(contract.contract_id, "legacy")
        assert legacy.status == ii.ActionStatus.CLAIMED
        assert provider.effect_count() == 0


@pytest.mark.parametrize("attempt", ["initial", "retry"])
def test_absence_observation_is_refreshable_if_inflight_submission_later_commits(
    tmp_path: Path, attempt: str,
) -> None:
    agent_path, provider_path = tmp_path / "agent.db", tmp_path / "provider.db"
    started, release = Event(), Event()

    class SlowSubmission(DurableProvider):
        def execute(self, request: object) -> object:
            started.set()
            if not release.wait(timeout=5):
                raise TimeoutError("test submission timed out")
            return super().execute(request)

    provider = SlowSubmission(provider_path)
    with ii.SQLiteEventStore(agent_path) as store, ii.SQLiteEventStore(agent_path) as observer:
        engine = ii.IntentIntegrityEngine(store, clock=lambda: NOW)
        contract = setup(engine)
        manager = coordinator(engine, provider)
        if attempt == "retry":
            failed = coordinator(engine, DurableProvider(provider_path, "error-before"))
            failed.execute(contract, ii.ActionRequest("p", "publish"), context(), operation())
            failed.reconcile(contract, "p")
        reader = coordinator(ii.IntentIntegrityEngine(observer, clock=lambda: NOW),
                             DurableProvider(provider_path))
        with ThreadPoolExecutor(max_workers=1) as pool:
            if attempt == "initial":
                future = pool.submit(manager.execute, contract, ii.ActionRequest("p", "publish"),
                                     context(), operation())
            else:
                future = pool.submit(manager.retry, contract, "p", context())
            try:
                assert started.wait(timeout=5)
                assert reader.reconcile(contract, "p").action.status == ii.ActionStatus.NOT_APPLIED
            finally:
                release.set()
            future.result(timeout=5)
        # A fresh read must discover the committed effect without any retry/write.
        recovered = reader.reconcile_pending(contract)
        assert recovered and recovered[0].action.status == ii.ActionStatus.SUCCEEDED
        assert provider.effect_count() == 1

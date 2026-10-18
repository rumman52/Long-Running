"""Demonstrate lost-response recovery using a separate local provider ledger."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from intent_integrity import (
    ActionRequest, ActionStatus, ExternalActionCoordinator, ExternalOperation,
    IntentContract, IntentIntegrityEngine, OutcomeStatus, PlanStep, ProviderOutcome,
    ProviderRequest, SQLiteEventStore, ValidationContext,
)


class LocalReportProvider:
    """Demo provider: atomic local effects, durable key binding, and consistent lookup."""

    provider_id = "local-report-demo-v1"
    idempotency_ttl_seconds = 300

    def __init__(self, path: Path, *, lose_response: bool = False) -> None:
        self.path = path
        self.lose_response = lose_response
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS reports "
                       "(key TEXT PRIMARY KEY, request TEXT NOT NULL)")

    def execute(self, request: ProviderRequest) -> ProviderOutcome:
        binding = json.dumps({"payload": request.payload, "version": request.expected_version},
                             sort_keys=True, allow_nan=False)
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT request FROM reports WHERE key = ?",
                               (request.idempotency_key,)).fetchone()
            if prior is not None:
                if prior[0] != binding:
                    return ProviderOutcome(OutcomeStatus.REJECTED, detail="Key/payload conflict")
            else:
                if datetime.now(UTC) >= request.idempotency_expires_at:
                    return ProviderOutcome(OutcomeStatus.REJECTED, detail="Deadline expired")
                if request.expected_version != "source-v1":
                    return ProviderOutcome(OutcomeStatus.REJECTED, detail="Source version changed")
                db.execute("INSERT INTO reports VALUES (?, ?)", (request.idempotency_key, binding))
        if self.lose_response:
            self.lose_response = False
            raise TimeoutError("Report committed; response lost")
        return ProviderOutcome(OutcomeStatus.SUCCEEDED, provider_reference=request.idempotency_key)

    def lookup(self, request: ProviderRequest) -> ProviderOutcome:
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            found = db.execute("SELECT key FROM reports WHERE key = ?",
                               (request.idempotency_key,)).fetchone()
        if found:
            return ProviderOutcome(OutcomeStatus.SUCCEEDED,
                                   provider_reference=request.idempotency_key)
        return ProviderOutcome(OutcomeStatus.NOT_APPLIED)


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        provider = LocalReportProvider(root / "provider.db", lose_response=True)
        contract = IntentContract("demo-external", 1, "Save exactly one report",
                                  permitted_actions=("save",), acceptance_criteria=("saved",))
        with SQLiteEventStore(root / "agent.db") as store:
            engine = IntentIntegrityEngine(store)
            engine.start_task(contract)
            engine.record_plan(contract, (PlanStep("save", "Save report", "save", ("saved",)),))
            coordinator = ExternalActionCoordinator(engine, (provider,))
            result = coordinator.execute(
                contract, ActionRequest("save-1", "save"),
                ValidationContext(datetime.now(UTC), active_contract_version=1),
                ExternalOperation(provider.provider_id, "report-42", {"report": "42"}, "source-v1"),
            )
            assert result.record is not None
            print("After lost response:", result.record.action.status.value)
            assert result.record.action.status == ActionStatus.UNKNOWN
        # A new engine and provider instance stand in for a restarted host.
        with SQLiteEventStore(root / "agent.db") as store:
            engine = IntentIntegrityEngine(store)
            coordinator = ExternalActionCoordinator(
                engine, (LocalReportProvider(root / "provider.db"),))
            recovered = coordinator.reconcile_pending(contract)[0]
            print("After outcome lookup:", recovered.action.status.value)
            with sqlite3.connect(root / "provider.db") as db:
                effects = db.execute("SELECT count(*) FROM reports").fetchone()[0]
            print("Provider reports stored:", effects)
            assert recovered.action.status == ActionStatus.SUCCEEDED and effects == 1


if __name__ == "__main__":
    main()

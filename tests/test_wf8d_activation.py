from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path

import pytest

from core.backtest.wf8_activation import (
    WF8ActivationError,
    WF8ProductionActivationService,
)
from core.backtest.wf8_reproducibility import WF8ReproducibilityManifestService
from data.database.sqlite_store import SQLiteStore
from tests.test_wf8c_reproducibility import _seed


def _store(tmp_path: Path) -> SQLiteStore:
    store=SQLiteStore(tmp_path/"activation.sqlite")
    store.initialize()
    _seed(store)
    return store


def test_activation_requires_verified_manifest_and_keeps_lkg_on_bad_candidate(tmp_path: Path) -> None:
    store=_store(tmp_path)
    try:
        repro=WF8ReproducibilityManifestService(store)
        m1=repro.create(hardening_id="HARD",code_identity="commit-a")
        service=WF8ProductionActivationService(store)
        a1=service.activate(manifest_id=m1.manifest_id)
        assert a1.status=="ACTIVE"

        m2=repro.create(hardening_id="HARD",code_identity="commit-b")
        # Corrupt only the candidate stored manifest hash; underlying evidence
        # remains valid, so the prior manifest is still a valid LKG.
        store.connection.execute(
            "UPDATE wf8_reproducibility_manifests SET chain_hash='bad' WHERE manifest_id=?",
            (m2.manifest_id,),
        )
        store.connection.commit()

        with pytest.raises(WF8ActivationError,match="candidate manifest failed"):
            service.activate(manifest_id=m2.manifest_id)
        assert service.active().activation_id==a1.activation_id
    finally:
        store.close()


def test_active_manifest_tamper_rolls_back_to_verified_standby(tmp_path: Path) -> None:
    store=_store(tmp_path)
    try:
        repro=WF8ReproducibilityManifestService(store)
        service=WF8ProductionActivationService(store)

        m1=repro.create(hardening_id="HARD",code_identity="commit-a")
        a1=service.activate(manifest_id=m1.manifest_id)

        m2=repro.create(hardening_id="HARD",code_identity="commit-b")
        a2=service.activate(manifest_id=m2.manifest_id)
        assert a2.activation_id != a1.activation_id
        assert service.active().activation_id==a2.activation_id

        store.connection.execute(
            "UPDATE wf8_reproducibility_manifests SET chain_hash='tampered' WHERE manifest_id=?",
            (m2.manifest_id,),
        )
        store.connection.commit()

        restored=service.resolve_active()
        assert restored.activation_id==a1.activation_id
        bad=store.connection.execute(
            "SELECT status FROM wf8_production_activations WHERE activation_id=?",
            (a2.activation_id,),
        ).fetchone()
        assert bad["status"]=="QUARANTINED"
        event=store.connection.execute(
            "SELECT event_type,to_activation_id FROM wf8_activation_events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert event["event_type"]=="AUTO_ROLLBACK"
        assert event["to_activation_id"]==a1.activation_id
    finally:
        store.close()


def test_no_lkg_fails_closed(tmp_path: Path) -> None:
    store=_store(tmp_path)
    try:
        repro=WF8ReproducibilityManifestService(store)
        service=WF8ProductionActivationService(store)
        m=repro.create(hardening_id="HARD",code_identity="commit-a")
        a=service.activate(manifest_id=m.manifest_id)
        store.connection.execute(
            "UPDATE wf8_reproducibility_manifests SET chain_hash='tampered' WHERE manifest_id=?",
            (m.manifest_id,),
        )
        store.connection.commit()
        with pytest.raises(WF8ActivationError,match="no verified LKG"):
            service.resolve_active()
        assert service.active() is None
    finally:
        store.close()

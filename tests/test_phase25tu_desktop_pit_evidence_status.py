from __future__ import annotations
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtWidgets import QApplication

from app.ui.historical_pit_evidence_service import (
    HistoricalPitEvidenceService,
)
from app.ui.historical_pit_evidence_dialog import (
    HistoricalPitEvidenceDialog, format_historical_pit_view,
)
from app.ui.main_window import ResearchTerminalWindow

FULL_SHA = "a" * 64

def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

def evidence(root):
    stage = root / "phase25q/staged_datasets" / ("research_pit_" + FULL_SHA[:16])
    _write(stage / "manifest.json", {
        "schema": "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1",
        "status": "RESEARCH_ONLY_NOT_CANONICAL_PIT",
        "staging_version": FULL_SHA,
        "period": {"start": "2024-01-01", "end": "2025-09-30"},
        "canonical_ready": False, "backtest_eligible_securities": 0,
        "production_DB_modified": False,
        "month_end_snapshots": 21,
        "monthly_membership_rows": 128088,
        "source_daily_valid_price_rows": 2110622,
    })
    _write(root / "phase25r/staging_readonly_reconciliation.json", {
        "schema": "MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1",
        "status": "21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL",
        "staging_version": FULL_SHA,
        "canonical_approved_rows": 0,
        "actual_WF9_executed": False,
        "actual_Learning_V3_executed": False,
        "production_DB_modified": False,
        "reconciled_strong_candidate_source_valid_rows": 1557903,
        "reconciled_3557_strong_monthly_price_candidates": 3557,
        "conflicting_month_ticker_exchange_identity_rows": 464,
        "conflicting_strong_cohort_tickers": ["B", "CWBC", "FUN", "STRR", "TEL", "TTE", "VIVO"],
    })
    _write(root / "phase25s/sitc_official_reverse_split_spinoff_price_diagnostics.json", {
        "schema": "MERIDYEN_PHASE25S_SITC_OFFICIAL_ACTION_SOURCE_PAIR_RESEARCH_V1",
        "status": "TWO_SEC_OFFICIAL_SITC_ACTION_EVENTS_DOCUMENTED_SOURCE_PRICES_NOT_CERTIFIED",
        "research_staging_version": FULL_SHA,
        "issuer_documented_actions": 2,
        "source_pair_diagnostics_computed": 2,
        "canonical_eligible_securities": 0,
        "WF9_executed": False,
        "Learning_V3_trained": False,
    })
    return stage

def test_missing_stage_is_not_interpreted_as_zero_approved_certification():
    with TemporaryDirectory() as tmp:
        v = HistoricalPitEvidenceService(Path(tmp)).snapshot()
        assert v.state == "NOT_VERIFIED"
        assert v.canonical_securities is None
        assert v.wf9 == "NO_VERIFIED_EXECUTION"
        assert v.learning_v3 == "NO_VERIFIED_TRAINING"

def test_real_source_status_is_distinct_from_canonical_and_training():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        evidence(root)
        v = HistoricalPitEvidenceService(root).snapshot()
        assert v.state == "RESEARCH_ONLY_NOT_CANONICAL"
        assert v.source_price_rows == 2110622
        assert v.independently_reconciled_price_rows == 1557903
        assert v.member_months == 21
        assert v.conflicting_source_identity_rows == 464
        assert v.canonical_securities == 0
        assert v.sitc_issuer_actions == 2
        assert v.sitc_real_price_pairs == 2
        assert v.wf9 == "BLOCKED_NO_CANONICAL_PIT"
        assert v.learning_v3 == "BLOCKED_NO_MATURE_PIT_LABELS"
        assert "NOT" not in dict(format_historical_pit_view(v))["Raw SimFin source daily price rows"]

def test_stale_or_forged_qa_does_not_count_verified_events():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        evidence(root)
        path = root / "phase25r/staging_readonly_reconciliation.json"
        stale = json.loads(path.read_text())
        stale["staging_version"] = "f" * 64
        path.write_text(json.dumps(stale))
        view = HistoricalPitEvidenceService(root).snapshot()
        assert view.independently_reconciled_price_rows is None
        assert view.conflicting_source_identity_rows is None
        assert view.canonical_securities == 0
        assert any("25R" in b for b in view.blockers)

def test_forged_canonical_flag_makes_manifest_unavailable():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        stage = evidence(root)
        f = stage / "manifest.json"
        data = json.loads(f.read_text())
        data["canonical_ready"] = True
        f.write_text(json.dumps(data))
        view = HistoricalPitEvidenceService(root).snapshot()
        assert view.state == "NOT_VERIFIED"
        assert view.canonical_securities is None

@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])

def test_native_desktop_button_opens_readonly_pit_dialog(qapp):
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        evidence(root)
        factory = lambda: HistoricalPitEvidenceService(root)
        window = ResearchTerminalWindow(historical_pit_service_factory=factory)
        try:
            window.pit_evidence_button.click()
            dialog = window._historical_pit_dialog
            assert isinstance(dialog, HistoricalPitEvidenceDialog)
            assert dialog.table.rowCount() >= 15
            assert "BLOCKED_NO_CANONICAL_PIT" in dialog.status.text()
            assert "BLOCKED_NO_MATURE_PIT_LABELS" in dialog.status.text()
            assert window.s16_page.status.text() == "NOT LOADED"
            assert window.s16_ea_page.status.text() == "NOT LOADED"
            assert "never starts" in dialog.note.text()
        finally:
            if hasattr(window, "_historical_pit_dialog"):
                window._historical_pit_dialog.close()
            window.close()

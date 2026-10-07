from datetime import date
from pathlib import Path
from types import SimpleNamespace

from core.backtest.production_evidence_chain import ProductionEvidenceChain
from data.database.sqlite_store import SQLiteStore


def test_production_evidence_preflight_fails_closed_on_empty_database(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "evidence.sqlite")
    store.initialize()
    try:
        app = SimpleNamespace(sqlite=store)
        report = ProductionEvidenceChain(app).preflight(
            start_date=date(1990, 1, 1),
            end_date=date(1990, 12, 31),
        )
        assert report.status == "BLOCKED"
        assert "NO_PIT_SNAPSHOT_DATES_IN_REQUESTED_WINDOW" in report.blocked_dates
    finally:
        store.close()

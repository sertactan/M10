from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.production_evidence_chain import ProductionEvidenceChain


def test_production_evidence_preflight_fails_closed_on_empty_database(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    app = AppContainer(root)
    app.initialize()
    try:
        # Use the app's initialized DB contract; an empty historical snapshot
        # window must never be promoted to READY.
        report = ProductionEvidenceChain(app).preflight(
            start_date=date(1990, 1, 1),
            end_date=date(1990, 12, 31),
        )
        assert report.status == "BLOCKED"
        assert "NO_PIT_SNAPSHOT_DATES_IN_REQUESTED_WINDOW" in report.blocked_dates
    finally:
        app.close()

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from core.contracts.enums import Exchange
from core.prices.engine import HistoricalPriceEngine
from core.prices.models import (
    AdjustmentStatus,
    PriceQualityStatus,
    SourcePriceBar,
)
from core.prices.validation import compare_adjusted_close
from data.database.sqlite_store import SQLiteStore
from data.repositories.price_repository import PriceRepository
from data.repositories.validation_repository import ValidationRepository


NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


class _Provider:
    def __init__(self, configured: bool = True) -> None:
        self.configured = configured


def _bar(source: str, day: int, close: float) -> SourcePriceBar:
    return SourcePriceBar(
        security_id="SEC_TEST",
        source=source,
        source_symbol="TEST",
        trade_date=date(2026, 10, day),
        open=close,
        high=close,
        low=close,
        raw_close=close,
        adjusted_close=close,
        volume=1000,
        retrieved_at=NOW,
        quality_status=(
            PriceQualityStatus.PRIMARY
            if source == "MASSIVE"
            else PriceQualityStatus.SECONDARY
        ),
        adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
    )


def test_price_divergence_thresholds_emit_diagnostics() -> None:
    primary = [_bar("MASSIVE", 1, 100.0), _bar("MASSIVE", 2, 100.0)]

    ok = compare_adjusted_close(
        primary,
        [_bar("SIMFIN", 1, 100.1), _bar("SIMFIN", 2, 100.2)],
    )
    warn = compare_adjusted_close(
        primary,
        [_bar("SIMFIN", 1, 101.0), _bar("SIMFIN", 2, 101.0)],
    )
    suspect = compare_adjusted_close(
        primary,
        [_bar("SIMFIN", 1, 105.0), _bar("SIMFIN", 2, 105.0)],
    )

    assert ok["status"] == "OK"
    assert warn["status"] == "WARN"
    assert suspect["status"] == "SUSPECT"


def test_confirmation_order_includes_massive_and_excludes_selected_source() -> None:
    providers = {
        "MASSIVE": _Provider(True),
        "MARKETPARQUET": _Provider(True),
        "SIMFIN": _Provider(True),
        "YAHOO_COMPAT": _Provider(True),
        "STOOQ": _Provider(True),
    }
    engine = HistoricalPriceEngine(None, providers)
    order = engine._validation_provider_order("MARKETPARQUET")

    assert order[0] == "MASSIVE"
    assert "MARKETPARQUET" not in order
    assert "YAHOO_COMPAT" in order


def test_validation_repository_makes_price_differences_queryable(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        # price_validation_results intentionally has no FK to a price series;
        # it is immutable comparison evidence with explicit provenance.
        store.connection.execute(
            """
            INSERT INTO price_validation_results (
                validation_id,security_id,start_date,end_date,source_a,source_b,
                overlap_rows,median_abs_pct_diff,max_abs_pct_diff,status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                "SEC_TEST",
                "2026-01-01",
                "2026-10-06",
                "MASSIVE",
                "SIMFIN",
                180,
                2.5,
                8.0,
                "SUSPECT",
                NOW.isoformat(),
            ),
        )
        store.connection.commit()

        summary = ValidationRepository(store).summary("SEC_TEST")

        assert summary["price"]["counts"] == {"SUSPECT": 1}
        assert summary["price"]["diagnostics"][0]["source_a"] == "MASSIVE"
        assert summary["price"]["diagnostics"][0]["source_b"] == "SIMFIN"
        assert summary["fundamentals"]["latest"] == []
    finally:
        store.close()

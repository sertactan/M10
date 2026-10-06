from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from core.historical.pilot_verification import (
    PilotHistoricalVerifier,
    PilotObservation,
    load_pilot_observations,
)
from core.prices.models import (
    AdjustmentStatus,
    PriceQualityStatus,
    SourcePriceBar,
)
from data.database.sqlite_store import SQLiteStore
from data.repositories.price_repository import PriceRepository
from data.storage.parquet_price_store import ParquetPriceStore


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


def _fake_app(tmp_path: Path):
    store = SQLiteStore(tmp_path / "pilot.sqlite")
    store.initialize()
    app = SimpleNamespace(
        sqlite=store,
        app_config=SimpleNamespace(
            database=SimpleNamespace(parquet_root="parquet")
        ),
        resolve_data_path=lambda configured: tmp_path / configured,
    )
    return app


def _insert_security(app, *, security_id: str, ticker: str) -> None:
    app.sqlite.connection.execute(
        """
        INSERT INTO security_master (
            security_id,ticker,name,exchange,market,active,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            security_id,
            ticker,
            ticker + " Inc.",
            "NASDAQ",
            "US",
            1,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    app.sqlite.connection.execute(
        """
        INSERT INTO ticker_aliases (
            alias,security_id,valid_from,valid_to,source,event_type,
            availability_date,ingested_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            ticker,
            security_id,
            "2010-01-01",
            None,
            "TEST",
            "listing",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    app.sqlite.connection.commit()


def _install_price_path(
    app,
    *,
    security_id: str,
    ticker: str,
    max_multiple: float,
    adjustment: AdjustmentStatus = AdjustmentStatus.DUAL_RAW_ADJUSTED,
    quality: PriceQualityStatus = PriceQualityStatus.PRIMARY,
) -> None:
    parquet = ParquetPriceStore(app.resolve_data_path("parquet"))
    repo = PriceRepository(app.sqlite, parquet)
    entry = 10.0
    bars: list[SourcePriceBar] = []
    anchor = date(2020, 1, 2)
    for i in range(253):
        trade_date = anchor + timedelta(days=i)
        ratio = 1.0 + (max_multiple - 1.0) * (i / 252.0)
        close = entry * ratio
        bars.append(
            SourcePriceBar(
                security_id=security_id,
                source="TEST",
                source_symbol=ticker,
                trade_date=trade_date,
                open=close,
                high=close,
                low=close,
                raw_close=close,
                adjusted_close=close,
                volume=1_000_000.0,
                retrieved_at=NOW,
                quality_status=quality,
                adjustment_status=adjustment,
            )
        )
    descriptor = repo.save_series(bars)
    repo.select_series(
        security_id=security_id,
        start=descriptor.start_date,
        end=descriptor.end_date,
        source=descriptor.source,
        source_symbol=descriptor.source_symbol,
        purpose="BACKTEST",
        reason="pilot verification test",
    )


def test_packaged_pilot_manifests_have_46_winners_and_150_controls():
    root = Path(__file__).resolve().parents[1]
    rows = load_pilot_observations(root / "data" / "seeds")
    winners = [row for row in rows if row.kind == "WINNER"]
    controls = [row for row in rows if row.kind == "CONTROL"]
    assert len(winners) == 46
    assert len(controls) == 150
    assert len(rows) == 196


def test_control_with_verified_fm252_below_10_becomes_valid(tmp_path: Path):
    app = _fake_app(tmp_path)
    try:
        _insert_security(app, security_id="SEC_CTRL", ticker="CTRL")
        _install_price_path(
            app,
            security_id="SEC_CTRL",
            ticker="CTRL",
            max_multiple=5.0,
        )
        result = PilotHistoricalVerifier(app).verify_one(
            PilotObservation(
                kind="CONTROL",
                observation_key="C_TEST",
                ticker="CTRL",
                anchor_group="2020",
            )
        )
        assert result.status == "VALID_CONTROL"
        assert result.outcome_status == "READY"
        assert result.fm252 is not None and 4.9 < result.fm252 < 5.1
        assert result.anchor_date == "2020-01-02"
    finally:
        app.sqlite.close()


def test_provisional_control_that_reaches_10x_is_rejected(tmp_path: Path):
    app = _fake_app(tmp_path)
    try:
        _insert_security(app, security_id="SEC_FALSE", ticker="FALSE")
        _install_price_path(
            app,
            security_id="SEC_FALSE",
            ticker="FALSE",
            max_multiple=12.0,
        )
        result = PilotHistoricalVerifier(app).verify_one(
            PilotObservation(
                kind="CONTROL",
                observation_key="C_FALSE",
                ticker="FALSE",
                anchor_group="2020",
            )
        )
        assert result.status == "REJECT_TRUE_10X"
        assert result.fm252 is not None and result.fm252 >= 10.0
        assert result.outcome_class == "TRUE_10X"
    finally:
        app.sqlite.close()


def test_winner_requires_canonical_fm252_at_least_10(tmp_path: Path):
    app = _fake_app(tmp_path)
    try:
        _insert_security(app, security_id="SEC_WIN", ticker="WIN")
        _install_price_path(
            app,
            security_id="SEC_WIN",
            ticker="WIN",
            max_multiple=11.0,
        )
        result = PilotHistoricalVerifier(app).verify_one(
            PilotObservation(
                kind="WINNER",
                observation_key="W_TEST",
                ticker="WIN",
                anchor_group="2020",
            )
        )
        assert result.status == "VERIFIED_WINNER"
        assert result.fm252 is not None and result.fm252 >= 10.0
    finally:
        app.sqlite.close()


def test_month_only_event_anchor_is_not_invented(tmp_path: Path):
    app = _fake_app(tmp_path)
    try:
        result = PilotHistoricalVerifier(app).verify_one(
            PilotObservation(
                kind="WINNER",
                observation_key="W_MONTH",
                ticker="NVAX",
                anchor_group="2020-03",
            )
        )
        assert result.status == "UNRESOLVED_ANCHOR"
        assert result.anchor_date is None
        assert "no day is invented" in (result.message or "")
    finally:
        app.sqlite.close()


def test_raw_only_backtest_selection_is_not_accepted(tmp_path: Path):
    app = _fake_app(tmp_path)
    try:
        _insert_security(app, security_id="SEC_RAW", ticker="RAW")
        _install_price_path(
            app,
            security_id="SEC_RAW",
            ticker="RAW",
            max_multiple=5.0,
            adjustment=AdjustmentStatus.RAW_ONLY,
            quality=PriceQualityStatus.BOOTSTRAP,
        )
        result = PilotHistoricalVerifier(app).verify_one(
            PilotObservation(
                kind="CONTROL",
                observation_key="C_RAW",
                ticker="RAW",
                anchor_group="2020",
            )
        )
        assert result.status == "MISSING_CANONICAL_PRICE"
    finally:
        app.sqlite.close()

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.forecast.calibration import ForecastCalibrationUnavailable
from core.forecast.empirical_provider import (
    MarketPrevalenceEmpiricalCalibrationProvider,
)
from data.database.sqlite_store import SQLiteStore


AS_OF = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _insert_security(store: SQLiteStore) -> None:
    store.connection.execute(
        """
        INSERT INTO security_master (
            security_id,ticker,name,exchange,market,active,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            "SEC_A","AAA","AAA Inc.","NASDAQ","US",1,
            AS_OF.isoformat(),AS_OF.isoformat(),
        ),
    )


def _seed_cohort(
    store: SQLiteStore,
    *,
    count: int,
    route: str,
    start_index: int = 0,
    score: float = 82.0,
) -> None:
    for offset in range(count):
        i = start_index + offset
        analysis_date = date(2020, 1, 1) + timedelta(days=i)
        analysis_id = f"A-{i:04d}"
        observation_id = f"SEC_A|{analysis_date.isoformat()}"

        if i % 4 == 0:
            fm252 = 1.5
        elif i % 4 == 1:
            fm252 = 2.5
        elif i % 4 == 2:
            fm252 = 5.5
        else:
            fm252 = 10.5

        store.connection.execute(
            """
            INSERT INTO analysis_runs (
                analysis_id,ticker,security_id,analysis_date,mode,model_version,
                data_snapshot_hash,model_config_hash,score,route,destination,prediction,
                status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                analysis_id,"AAA","SEC_A",analysis_date.isoformat(),
                "MARKET_PREVALENCE","S15.3_V1.4",
                "a"*64,"b"*64,score,route,None,None,"READY",AS_OF.isoformat(),
            ),
        )
        store.connection.execute(
            """
            INSERT INTO backtest_results (
                analysis_id,entry_price,return_1m,return_3m,return_6m,return_12m,
                max_gain_12m,max_drawdown_12m,result_class,outcome_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                analysis_id,10.0,None,None,None,float(i),
                None,None,"CALIBRATION","READY",
            ),
        )
        store.connection.execute(
            """
            INSERT INTO forward_outcomes (
                observation_id,security_id,as_of_date_requested,anchor_session,
                anchor_lag_calendar_days,entry_adjusted_close,horizon_sessions_available,
                fm252,max_multiple_observed,outcome_class,time_to_2x_sessions,
                time_to_3x_sessions,time_to_5x_sessions,time_to_7x_sessions,
                time_to_10x_sessions,outcome_status,diagnostics_json,outcome_hash,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                observation_id,"SEC_A",analysis_date.isoformat(),analysis_date.isoformat(),
                0,10.0,252,fm252,fm252,
                "TRUE_10X" if fm252 >= 10 else "OTHER",
                None,None,None,None,None,"READY","{}","c"*64,AS_OF.isoformat(),
            ),
        )
    store.connection.commit()


def _models(*, score: float = 84.0, route: str = "F10"):
    v12 = SimpleNamespace(score=80.0, confidence=78.0)
    v14 = SimpleNamespace(
        score=score,
        primary_route=route,
        confidence=86.0,
    )
    return v12, v14


def test_empirical_calibration_uses_score_route_cohort_and_p20_p50_p80(tmp_path):
    store = SQLiteStore(tmp_path / "cal.sqlite")
    store.initialize()
    try:
        _insert_security(store)
        _seed_cohort(store, count=40, route="F10")
        provider = MarketPrevalenceEmpiricalCalibrationProvider(store)
        v12, v14 = _models()

        result = provider.calibrate(
            v12=v12,
            v14=v14,
            as_of=AS_OF,
            horizon_months=12,
        )

        assert result.sample_size == 40
        assert result.metadata["score_band"] == "80-89"
        assert result.metadata["cohort_scope"] == "SCORE_BAND_ROUTE"
        assert result.metadata["sample_quality"] == "REDUCED_SAMPLE"
        assert result.bear_return_pct == pytest.approx(7.8)
        assert result.base_return_pct == pytest.approx(19.5)
        assert result.bull_return_pct == pytest.approx(31.2)
        assert result.probability_positive_return_pct == pytest.approx(97.5)
        assert result.probability_2x_plus_pct == pytest.approx(75.0)
        assert result.probability_5x_plus_pct == pytest.approx(50.0)
        assert result.probability_10x_plus_pct == pytest.approx(25.0)
        assert result.confidence_pct == pytest.approx(86.0)
        assert result.risk == "EMPIRICAL_P20_DOWNSIDE"
    finally:
        store.close()


def test_empirical_calibration_widens_route_when_exact_cohort_below_30(tmp_path):
    store = SQLiteStore(tmp_path / "cal.sqlite")
    store.initialize()
    try:
        _insert_security(store)
        _seed_cohort(store, count=20, route="F10", start_index=0)
        _seed_cohort(store, count=20, route="I10", start_index=20)
        provider = MarketPrevalenceEmpiricalCalibrationProvider(store)
        v12, v14 = _models(route="F10")

        result = provider.calibrate(
            v12=v12,
            v14=v14,
            as_of=AS_OF,
            horizon_months=12,
        )

        assert result.sample_size == 40
        assert result.metadata["cohort_scope"] == "SCORE_BAND"
    finally:
        store.close()


def test_empirical_calibration_fails_closed_below_minimum_sample(tmp_path):
    store = SQLiteStore(tmp_path / "cal.sqlite")
    store.initialize()
    try:
        _insert_security(store)
        _seed_cohort(store, count=29, route="F10")
        provider = MarketPrevalenceEmpiricalCalibrationProvider(store)
        v12, v14 = _models()

        with pytest.raises(ForecastCalibrationUnavailable, match="too small"):
            provider.calibrate(
                v12=v12,
                v14=v14,
                as_of=AS_OF,
                horizon_months=12,
            )
    finally:
        store.close()


def test_empirical_calibration_refuses_non_market_prevalence_rows(tmp_path):
    store = SQLiteStore(tmp_path / "cal.sqlite")
    store.initialize()
    try:
        _insert_security(store)
        _seed_cohort(store, count=30, route="F10")
        store.connection.execute(
            "UPDATE analysis_runs SET mode='HISTORICAL'"
        )
        store.connection.commit()

        provider = MarketPrevalenceEmpiricalCalibrationProvider(store)
        v12, v14 = _models()
        with pytest.raises(ForecastCalibrationUnavailable, match="too small"):
            provider.calibrate(
                v12=v12,
                v14=v14,
                as_of=AS_OF,
                horizon_months=12,
            )
    finally:
        store.close()


def test_empirical_calibration_fails_closed_for_scores_below_recovered_bands(tmp_path):
    store = SQLiteStore(tmp_path / "cal.sqlite")
    store.initialize()
    try:
        _insert_security(store)
        provider = MarketPrevalenceEmpiricalCalibrationProvider(store)
        v12, v14 = _models(score=49.0)
        with pytest.raises(ForecastCalibrationUnavailable, match="below 50"):
            provider.calibrate(
                v12=v12,
                v14=v14,
                as_of=AS_OF,
                horizon_months=12,
            )
    finally:
        store.close()

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone

from core.forecast.calibration import ForecastCalibrationUnavailable
from core.forecast.contracts import CalibratedForecast
from core.models.s153_v12_contracts import S153V12Result
from core.models.s153_v14_contracts import S153V14Result
from data.database.sqlite_store import SQLiteStore


SCORE_BANDS = (
    (50.0, 60.0, "50-59"),
    (60.0, 70.0, "60-69"),
    (70.0, 80.0, "70-79"),
    (80.0, 90.0, "80-89"),
    (90.0, 101.0, "90+"),
)

MIN_COHORT_SIZE = 30
FULL_COHORT_SIZE = 50


def _score_band(score: float) -> tuple[float, float, str] | None:
    for low, high, label in SCORE_BANDS:
        if low <= score < high:
            return low, high, label
    return None


def _percentile(values: list[float], q: float) -> float:
    if not values:
        raise ForecastCalibrationUnavailable("Calibration cohort has no realized returns")
    if not 0.0 <= q <= 1.0:
        raise ValueError("percentile q must be in [0,1]")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _pct(count: int, total: int) -> float:
    return 100.0 * float(count) / float(total)


class MarketPrevalenceEmpiricalCalibrationProvider:
    """Historical Phase-6 calibration recovered from the prior project rules.

    Rules preserved from the earlier design:
    - calibration is empirical, never hard-coded;
    - use Market Prevalence / walk-forward observations only;
    - select a V1.4 score band and same-route cohort first;
    - if the exact route cohort is <30, widen to the score band;
    - <30 observations after widening is unavailable;
    - 2X/5X/10X are realized cohort frequencies;
    - bear/base/bull are P20/P50/P80 realized 12M returns.

    No new confidence weighting or LOW/MEDIUM/HIGH risk threshold is invented.
    Numeric confidence is the canonical V1.4 confidence (fallback V1.2).
    Historical P20 downside is exposed in metadata/risk text.
    """

    def __init__(
        self,
        store: SQLiteStore,
        *,
        model_version: str = "S15.3_V1.4",
    ) -> None:
        self.store = store
        self.model_version = model_version

    def _rows(
        self,
        *,
        as_of: datetime,
        low: float,
        high: float,
        route: str | None,
    ):
        where_route = "AND a.route=?" if route else ""
        params: list[object] = [
            self.model_version,
            low,
            high,
            as_of.date().isoformat(),
        ]
        if route:
            params.append(route)
        return self.store.connection.execute(
            f"""
            SELECT
                a.analysis_id,
                a.security_id,
                a.analysis_date,
                a.score,
                a.route,
                b.return_12m,
                o.fm252
            FROM analysis_runs a
            JOIN backtest_results b
              ON b.analysis_id=a.analysis_id
            JOIN forward_outcomes o
              ON o.security_id=a.security_id
             AND o.as_of_date_requested=a.analysis_date
            WHERE a.model_version=?
              AND a.mode='MARKET_PREVALENCE'
              AND a.status='READY'
              AND b.outcome_status='READY'
              AND o.outcome_status='READY'
              AND a.score>=?
              AND a.score<?
              AND a.analysis_date<?
              AND b.return_12m IS NOT NULL
              AND o.fm252 IS NOT NULL
              {where_route}
            ORDER BY a.analysis_date,a.analysis_id
            """,
            tuple(params),
        ).fetchall()

    def calibrate(
        self,
        *,
        v12: S153V12Result,
        v14: S153V14Result,
        as_of: datetime,
        horizon_months: int,
    ) -> CalibratedForecast:
        if as_of.tzinfo is None:
            raise ValueError("forecast as_of must be timezone-aware")
        if horizon_months != 12:
            raise ValueError("Empirical calibration supports only 12 months")
        if v14.score is None:
            raise ForecastCalibrationUnavailable("V1.4 score is unavailable")

        band = _score_band(float(v14.score))
        if band is None:
            raise ForecastCalibrationUnavailable(
                "No recovered calibration score band exists below 50"
            )
        low, high, label = band
        route = getattr(v14, "primary_route", None)

        exact = self._rows(
            as_of=as_of,
            low=low,
            high=high,
            route=route,
        )
        cohort = exact
        scope = "SCORE_BAND_ROUTE"

        if len(cohort) < MIN_COHORT_SIZE:
            cohort = self._rows(
                as_of=as_of,
                low=low,
                high=high,
                route=None,
            )
            scope = "SCORE_BAND"

        if len(cohort) < MIN_COHORT_SIZE:
            raise ForecastCalibrationUnavailable(
                f"Market Prevalence cohort too small: {len(cohort)} < {MIN_COHORT_SIZE}"
            )

        returns = [float(row["return_12m"]) for row in cohort]
        fm252 = [float(row["fm252"]) for row in cohort]
        total = len(cohort)

        bear = _percentile(returns, 0.20)
        base = _percentile(returns, 0.50)
        bull = _percentile(returns, 0.80)

        positive = _pct(sum(value > 0.0 for value in returns), total)
        p2 = _pct(sum(value >= 2.0 for value in fm252), total)
        p5 = _pct(sum(value >= 5.0 for value in fm252), total)
        p10 = _pct(sum(value >= 10.0 for value in fm252), total)

        confidence = getattr(v14, "confidence", None)
        confidence_source = "V1.4"
        if confidence is None:
            confidence = getattr(v12, "confidence", None)
            confidence_source = "V1.2"
        if confidence is None:
            raise ForecastCalibrationUnavailable(
                "Canonical model confidence is unavailable"
            )

        sample_quality = "NORMAL" if total >= FULL_COHORT_SIZE else "REDUCED_SAMPLE"
        max_analysis_date = max(str(row["analysis_date"]) for row in cohort)

        identity = {
            "model_version": self.model_version,
            "score_band": label,
            "route": route,
            "scope": scope,
            "sample_size": total,
            "max_analysis_date": max_analysis_date,
            "bear_p20": bear,
            "base_p50": base,
            "bull_p80": bull,
            "positive": positive,
            "p2": p2,
            "p5": p5,
            "p10": p10,
        }
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]

        return CalibratedForecast(
            calibration_id=f"EMP-{digest}",
            calibration_source="PHASE6_MARKET_PREVALENCE_EMPIRICAL_P20_P50_P80",
            calibration_cutoff=as_of.astimezone(timezone.utc),
            sample_size=total,
            bull_return_pct=bull,
            base_return_pct=base,
            bear_return_pct=bear,
            probability_positive_return_pct=positive,
            probability_2x_plus_pct=p2,
            probability_5x_plus_pct=p5,
            probability_10x_plus_pct=p10,
            confidence_pct=float(confidence),
            risk="EMPIRICAL_P20_DOWNSIDE",
            metadata={
                "dataset_kind": "MARKET_PREVALENCE",
                "calibration_method": "EMPIRICAL_SCORE_ROUTE_COHORT_P20_P50_P80",
                "score_band": label,
                "route": route,
                "cohort_scope": scope,
                "sample_quality": sample_quality,
                "confidence_source": confidence_source,
                "historical_max_analysis_date": max_analysis_date,
                "bear_percentile": 20,
                "base_percentile": 50,
                "bull_percentile": 80,
                "risk_p20_return_pct": bear,
            },
        )

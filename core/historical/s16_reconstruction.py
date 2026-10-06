from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Iterable, Mapping

from core.historical.s16_feature_coverage import (
    S16_REQUIRED_FEATURES,
    assess_feature_coverage,
)
from data.repositories.s16_evidence_repository import S16EvidenceRepository


DIRECT_EVIDENCE_FEATURES = {
    "ownership_lock",
    "catalyst",
    "regime_sympathy",
    "catalyst_proximity",
    "theme",
    "dilution_risk",
    "manipulation_risk",
}


@dataclass(frozen=True)
class S16RawHistoricalObservation:
    security_id: str
    ticker: str
    as_of: datetime
    float_shares: float
    price: float
    last_volume: float
    avg_volume20: float
    volatility10: float
    volatility20: float
    volatility60: float
    return_1d: float
    momentum5: float
    momentum20: float
    supply_kind: str = "FREE_FLOAT"
    source_quality: str = "PIT_EXACT"
    market_cap: float | None = None


@dataclass(frozen=True)
class S16ReconstructedSnapshot:
    security_id: str
    ticker: str
    as_of: datetime
    features: Mapping[str, float | None]
    evidence: Mapping[str, object]
    coverage_pct: float
    missing: tuple[str, ...]
    score_ready: bool


def _percentile(values: list[float], value: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    ordered = sorted(float(x) for x in values)
    if len(ordered) == 1:
        return 50.0
    less = sum(x < value for x in ordered)
    equal = sum(x == value for x in ordered)
    rank = less + 0.5 * equal
    return 100.0 * rank / len(ordered)


def _safe_ratio(a: float, b: float) -> float | None:
    if b <= 0:
        return None
    return float(a) / float(b)


def _attention_velocity(
    rows: Iterable[dict],
    *,
    as_of: datetime,
) -> tuple[float | None, dict[str, object]]:
    items = []
    for row in rows:
        observed = datetime.fromisoformat(str(row["observed_at"]))
        if observed.tzinfo is None:
            raise ValueError("attention observed_at must be timezone-aware")
        if observed <= as_of:
            items.append((observed, float(row["mentions"])))
    if not items:
        return None, {"reason": "no_attention_rows"}

    recent_start = as_of - timedelta(days=1)
    baseline_start = as_of - timedelta(days=21)
    recent = sum(value for observed, value in items if recent_start < observed <= as_of)
    baseline = sum(
        value
        for observed, value in items
        if baseline_start < observed <= recent_start
    )
    baseline_days = 20.0
    baseline_daily = baseline / baseline_days
    if baseline_daily <= 0:
        return None, {
            "recent_mentions": recent,
            "baseline_mentions": baseline,
            "reason": "non_positive_baseline",
        }
    velocity = recent / baseline_daily
    return velocity, {
        "recent_mentions": recent,
        "baseline_mentions": baseline,
        "baseline_daily": baseline_daily,
        "velocity": velocity,
    }


def _direct_feature(
    repo: S16EvidenceRepository,
    *,
    security_id: str,
    feature_key: str,
    as_of: datetime,
) -> tuple[float | None, dict[str, object]]:
    row = repo.latest_feature_evidence_as_of(security_id, feature_key, as_of)
    if row is None:
        return None, {"reason": "missing_direct_evidence"}
    value = float(row["value"])
    if feature_key.endswith("_risk"):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{feature_key} evidence must be in [0,1]")
    elif not 0.0 <= value <= 100.0:
        raise ValueError(f"{feature_key} evidence must be in [0,100]")
    return value, {
        "source": row["source"],
        "source_ref": row["source_ref"],
        "observed_at": row["observed_at"],
        "available_at": row["available_at"],
        "quality_status": row["quality_status"],
    }


class S16HistoricalFeatureReconstructor:
    """Reconstruct S16 inputs using only evidence available at each as-of instant.

    Cross-sectional market features are normalized against observations from the
    exact same as-of instant. Missing external evidence remains missing.
    """

    VERSION = "s16-historical-reconstruction-v2"

    def __init__(self, evidence: S16EvidenceRepository) -> None:
        self.evidence = evidence

    def reconstruct_batch(
        self,
        observations: Iterable[S16RawHistoricalObservation],
    ) -> list[S16ReconstructedSnapshot]:
        rows = list(observations)
        if not rows:
            return []
        as_of_values = {row.as_of for row in rows}
        if len(as_of_values) != 1:
            raise ValueError("reconstruct_batch requires one exact as_of timestamp")
        as_of = rows[0].as_of

        float_values = [math.log(max(row.float_shares, 1.0)) for row in rows]
        market_cap_raw = [
            (float(row.market_cap) if row.market_cap is not None and row.market_cap > 0
             else row.price * row.float_shares)
            for row in rows
        ]
        market_cap_values = [math.log(max(value, 1.0)) for value in market_cap_raw]
        turnover_raw = [
            row.last_volume / row.float_shares
            if row.float_shares > 0 else 0.0
            for row in rows
        ]
        rvol_raw = [
            row.last_volume / row.avg_volume20
            if row.avg_volume20 > 0 else 0.0
            for row in rows
        ]
        dollar_liquidity = [
            row.price * row.avg_volume20
            for row in rows
        ]
        elasticity_raw = [
            row.volatility20 / max(dollar_liquidity[i], 1.0)
            for i, row in enumerate(rows)
        ]
        momentum_accel_raw = [
            row.return_1d - row.momentum5 / 5.0
            for row in rows
        ]
        compression_raw = [
            row.volatility10 / row.volatility60
            if row.volatility60 > 0 else math.inf
            for row in rows
        ]
        extension_raw = [max(0.0, row.momentum5) for row in rows]

        short_ratio_raw: list[float] = []
        dtc_raw: list[float] = []
        short_by_security: dict[str, tuple[float | None, float | None, dict]] = {}
        social_velocity_raw: list[float] = []
        news_velocity_raw: list[float] = []
        social_by_security: dict[str, tuple[float | None, dict]] = {}
        news_by_security: dict[str, tuple[float | None, dict]] = {}

        for row in rows:
            short = self.evidence.latest_short_interest_as_of(row.security_id, as_of)
            if short is None:
                short_by_security[row.security_id] = (None, None, {"reason": "missing_short_interest"})
            else:
                denominator = (
                    float(short["float_shares"])
                    if short.get("float_shares") not in (None, 0)
                    else row.float_shares
                )
                ratio = (
                    float(short["short_interest"]) / denominator
                    if denominator > 0 else None
                )
                dtc = (
                    float(short["days_to_cover"])
                    if short.get("days_to_cover") is not None
                    else (
                        float(short["short_interest"]) / row.avg_volume20
                        if row.avg_volume20 > 0 else None
                    )
                )
                meta = {
                    "settlement_date": short["settlement_date"],
                    "available_at": short["available_at"],
                    "source": short["source"],
                    "source_ref": short["source_ref"],
                }
                short_by_security[row.security_id] = (ratio, dtc, meta)
                if ratio is not None:
                    short_ratio_raw.append(ratio)
                if dtc is not None:
                    dtc_raw.append(dtc)

            social_velocity, social_meta = _attention_velocity(
                self.evidence.attention_as_of(row.security_id, "SOCIAL", as_of),
                as_of=as_of,
            )
            news_velocity, news_meta = _attention_velocity(
                self.evidence.attention_as_of(row.security_id, "NEWS", as_of),
                as_of=as_of,
            )
            social_by_security[row.security_id] = (social_velocity, social_meta)
            news_by_security[row.security_id] = (news_velocity, news_meta)
            if social_velocity is not None:
                social_velocity_raw.append(social_velocity)
            if news_velocity is not None:
                news_velocity_raw.append(news_velocity)

        snapshots: list[S16ReconstructedSnapshot] = []
        for i, row in enumerate(rows):
            market_cap_scarcity = 100.0 - _percentile(
                market_cap_values, math.log(max(market_cap_raw[i], 1.0))
            )
            float_scarcity = 100.0 - _percentile(
                float_values, math.log(max(row.float_shares, 1.0))
            )
            turnover_score = _percentile(turnover_raw, turnover_raw[i])
            rvol_score = _percentile(rvol_raw, rvol_raw[i])
            liquidity_elasticity = _percentile(elasticity_raw, elasticity_raw[i])
            momentum_acceleration = _percentile(
                momentum_accel_raw, momentum_accel_raw[i]
            )
            compression = 100.0 - _percentile(
                compression_raw, compression_raw[i]
            )
            extension_risk = _percentile(extension_raw, extension_raw[i]) / 100.0
            liquidity_risk = (
                100.0 - _percentile(dollar_liquidity, dollar_liquidity[i])
            ) / 100.0
            volume_ignition = 0.60 * rvol_score + 0.40 * turnover_score

            short_ratio, dtc, short_meta = short_by_security[row.security_id]
            if short_ratio is None or dtc is None or not short_ratio_raw or not dtc_raw:
                short_pressure = None
            else:
                short_pressure = (
                    0.70 * _percentile(short_ratio_raw, short_ratio)
                    + 0.30 * _percentile(dtc_raw, dtc)
                )

            social_velocity_value, social_meta = social_by_security[row.security_id]
            news_velocity_value, news_meta = news_by_security[row.security_id]
            social_velocity = (
                _percentile(social_velocity_raw, social_velocity_value)
                if social_velocity_value is not None and social_velocity_raw
                else None
            )
            news_velocity = (
                _percentile(news_velocity_raw, news_velocity_value)
                if news_velocity_value is not None and news_velocity_raw
                else None
            )

            direct_values: dict[str, float | None] = {}
            direct_meta: dict[str, object] = {}
            for feature_key in DIRECT_EVIDENCE_FEATURES:
                value, meta = _direct_feature(
                    self.evidence,
                    security_id=row.security_id,
                    feature_key=feature_key,
                    as_of=as_of,
                )
                direct_values[feature_key] = value
                direct_meta[feature_key] = meta

            attention_candidates = [
                x for x in (social_velocity, news_velocity) if x is not None
            ]
            attention = (
                mean(attention_candidates)
                if attention_candidates
                else None
            )
            anomaly = mean(sorted(
                [turnover_score, rvol_score, momentum_acceleration],
                reverse=True,
            )[:2])

            proxy_penalty = 0.20 if row.source_quality != "PIT_EXACT" else 0.0
            short_age_penalty = 0.0
            if short_meta.get("available_at"):
                short_age = (
                    as_of - datetime.fromisoformat(str(short_meta["available_at"]))
                ).total_seconds() / 86400.0
                short_age_penalty = min(0.35, max(0.0, short_age) / 60.0 * 0.35)
            data_risk = min(1.0, proxy_penalty + short_age_penalty)

            features: dict[str, float | None] = {
                "market_cap_scarcity": market_cap_scarcity,
                "float_scarcity": float_scarcity,
                "short_pressure": short_pressure,
                "float_turnover": turnover_score,
                "liquidity_elasticity": liquidity_elasticity,
                "ownership_lock": direct_values["ownership_lock"],
                "catalyst": direct_values["catalyst"],
                "volume_ignition": volume_ignition,
                "momentum_acceleration": momentum_acceleration,
                "social_velocity": social_velocity,
                "news_velocity": news_velocity,
                "regime_sympathy": direct_values["regime_sympathy"],
                "attention": attention,
                "compression": compression,
                "catalyst_proximity": direct_values["catalyst_proximity"],
                "theme": direct_values["theme"],
                "anomaly": anomaly,
                "dilution_risk": direct_values["dilution_risk"],
                "extension_risk": extension_risk,
                "data_risk": data_risk,
                "liquidity_risk": liquidity_risk,
                "manipulation_risk": direct_values["manipulation_risk"],
            }
            coverage = assess_feature_coverage(features)
            evidence = {
                "version": self.VERSION,
                "cross_section_size": len(rows),
                "raw": {
                    "market_cap": market_cap_raw[i],
                    "market_cap_source": (
                        "PIT_MARKET_CAP" if row.market_cap is not None and row.market_cap > 0
                        else "PRICE_X_FLOAT_PROXY"
                    ),
                    "float_turnover": turnover_raw[i],
                    "rvol": rvol_raw[i],
                    "dollar_liquidity": dollar_liquidity[i],
                    "liquidity_elasticity": elasticity_raw[i],
                    "momentum_acceleration": momentum_accel_raw[i],
                    "compression_ratio": compression_raw[i],
                    "extension_mom5": extension_raw[i],
                },
                "short": short_meta,
                "social": social_meta,
                "news": news_meta,
                "direct": direct_meta,
                "supply_kind": row.supply_kind,
                "source_quality": row.source_quality,
            }
            snapshots.append(S16ReconstructedSnapshot(
                security_id=row.security_id,
                ticker=row.ticker,
                as_of=row.as_of,
                features=features,
                evidence=evidence,
                coverage_pct=coverage.coverage_pct,
                missing=coverage.missing,
                score_ready=coverage.score_ready,
            ))
        return snapshots

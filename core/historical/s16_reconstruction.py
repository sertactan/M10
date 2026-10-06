from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping

from core.historical.s16_feature_coverage import assess_feature_coverage
from core.historical.s16_feature_engine import (
    canonical_attention,
    canonical_catalyst,
    canonical_momentum_acceleration,
    canonical_short_pressure,
    canonical_social_velocity,
    canonical_volume_ignition,
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

SUBFEATURE_EVIDENCE_KEYS = {
    "borrow_pressure",
    "ftd_pressure",
    "premarket_turnover",
    "catalyst_materiality",
    "catalyst_surprise",
    "catalyst_credibility",
    "catalyst_market_cap_impact",
    "catalyst_novelty",
    "catalyst_immediacy",
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
    volume_acceleration_raw: float = 1.0
    range_expansion_raw: float = 1.0
    close_location_raw: float = 0.5
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


def _attention_stats(
    rows: Iterable[dict],
    *,
    as_of: datetime,
) -> tuple[float | None, float | None, float | None, dict[str, object]]:
    items: list[tuple[datetime, float, float | None]] = []
    for row in rows:
        observed = datetime.fromisoformat(str(row["observed_at"]))
        if observed.tzinfo is None:
            raise ValueError("attention observed_at must be timezone-aware")
        if observed <= as_of:
            unique = (
                float(row["unique_authors"])
                if row.get("unique_authors") is not None
                else None
            )
            items.append((observed, float(row["mentions"]), unique))
    if not items:
        return None, None, None, {"reason": "no_attention_rows"}

    recent_start = as_of - timedelta(days=1)
    baseline_start = as_of - timedelta(days=21)
    recent_mentions = sum(
        mentions for observed, mentions, _ in items
        if recent_start < observed <= as_of
    )
    baseline_mentions = sum(
        mentions for observed, mentions, _ in items
        if baseline_start < observed <= recent_start
    )
    recent_authors = sum(
        authors for observed, _, authors in items
        if authors is not None and recent_start < observed <= as_of
    )
    baseline_authors = sum(
        authors for observed, _, authors in items
        if authors is not None and baseline_start < observed <= recent_start
    )

    baseline_daily_mentions = baseline_mentions / 20.0
    mention_velocity = (
        recent_mentions / baseline_daily_mentions
        if baseline_daily_mentions > 0 else None
    )

    baseline_daily_authors = baseline_authors / 20.0
    author_velocity = (
        recent_authors / baseline_daily_authors
        if recent_authors > 0 and baseline_daily_authors > 0
        else None
    )

    concentration_risk = None
    if recent_mentions > 0 and recent_authors > 0:
        diversity = min(1.0, recent_authors / recent_mentions)
        concentration_risk = 100.0 * (1.0 - diversity)

    return mention_velocity, author_velocity, concentration_risk, {
        "recent_mentions": recent_mentions,
        "baseline_mentions": baseline_mentions,
        "recent_unique_authors": recent_authors,
        "baseline_unique_authors": baseline_authors,
        "mention_velocity": mention_velocity,
        "unique_author_velocity": author_velocity,
        "concentration_risk": concentration_risk,
    }


def _feature_evidence(
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
    """Canonical S16 V1 feature reconstruction using PIT evidence only."""

    VERSION = "s16-historical-reconstruction-v3-feature-complete"

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
            (
                float(row.market_cap)
                if row.market_cap is not None and row.market_cap > 0
                else row.price * row.float_shares
            )
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
        dollar_liquidity = [row.price * row.avg_volume20 for row in rows]
        elasticity_raw = [
            row.volatility20 / max(dollar_liquidity[i], 1.0)
            for i, row in enumerate(rows)
        ]
        return_accel_raw = [
            row.return_1d - row.momentum5 / 5.0
            for row in rows
        ]
        compression_raw = [
            row.volatility10 / row.volatility60
            if row.volatility60 > 0 else math.inf
            for row in rows
        ]
        extension_raw = [max(0.0, row.momentum5) for row in rows]
        return_1d_raw = [row.return_1d for row in rows]
        volume_acceleration_raw = [row.volume_acceleration_raw for row in rows]
        range_expansion_raw = [row.range_expansion_raw for row in rows]
        close_location_raw = [row.close_location_raw for row in rows]

        short_ratio_raw: list[float] = []
        dtc_raw: list[float] = []
        si_accel_raw: list[float] = []
        short_by_security: dict[
            str, tuple[float | None, float | None, float | None, dict[str, object]]
        ] = {}

        channel_raw: dict[str, dict[str, tuple[float | None, float | None, float | None, dict]]] = {
            "SOCIAL": {},
            "NEWS": {},
            "SEARCH": {},
        }
        channel_mentions: dict[str, list[float]] = {key: [] for key in channel_raw}
        channel_authors: dict[str, list[float]] = {key: [] for key in channel_raw}

        direct_by_security: dict[str, dict[str, float | None]] = {}
        direct_meta_by_security: dict[str, dict[str, object]] = {}

        for row in rows:
            history = self.evidence.short_interest_history_as_of(
                row.security_id, as_of, limit=2
            )
            if not history:
                short_by_security[row.security_id] = (
                    None, None, None, {"reason": "missing_short_interest"}
                )
            else:
                current = history[0]
                denominator = (
                    float(current["float_shares"])
                    if current.get("float_shares") not in (None, 0)
                    else row.float_shares
                )
                ratio = (
                    float(current["short_interest"]) / denominator
                    if denominator > 0 else None
                )
                dtc = (
                    float(current["days_to_cover"])
                    if current.get("days_to_cover") is not None
                    else (
                        float(current["short_interest"]) / row.avg_volume20
                        if row.avg_volume20 > 0 else None
                    )
                )
                si_accel = None
                if len(history) >= 2 and float(history[1]["short_interest"]) > 0:
                    si_accel = (
                        float(current["short_interest"])
                        / float(history[1]["short_interest"])
                        - 1.0
                    )
                meta = {
                    "settlement_date": current["settlement_date"],
                    "available_at": current["available_at"],
                    "source": current["source"],
                    "source_ref": current["source_ref"],
                    "previous_settlement_date": (
                        history[1]["settlement_date"] if len(history) >= 2 else None
                    ),
                    "si_acceleration_raw": si_accel,
                }
                short_by_security[row.security_id] = (ratio, dtc, si_accel, meta)
                if ratio is not None:
                    short_ratio_raw.append(ratio)
                if dtc is not None:
                    dtc_raw.append(dtc)
                if si_accel is not None:
                    si_accel_raw.append(si_accel)

            for channel in ("SOCIAL", "NEWS", "SEARCH"):
                stats = _attention_stats(
                    self.evidence.attention_as_of(row.security_id, channel, as_of),
                    as_of=as_of,
                )
                channel_raw[channel][row.security_id] = stats
                mention_velocity, author_velocity, _, _ = stats
                if mention_velocity is not None:
                    channel_mentions[channel].append(mention_velocity)
                if author_velocity is not None:
                    channel_authors[channel].append(author_velocity)

            direct_values: dict[str, float | None] = {}
            direct_meta: dict[str, object] = {}
            for feature_key in DIRECT_EVIDENCE_FEATURES | SUBFEATURE_EVIDENCE_KEYS:
                value, meta = _feature_evidence(
                    self.evidence,
                    security_id=row.security_id,
                    feature_key=feature_key,
                    as_of=as_of,
                )
                direct_values[feature_key] = value
                direct_meta[feature_key] = meta
            direct_by_security[row.security_id] = direct_values
            direct_meta_by_security[row.security_id] = direct_meta

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
            volume_accel_score = _percentile(
                volume_acceleration_raw, volume_acceleration_raw[i]
            )
            liquidity_elasticity = _percentile(
                elasticity_raw, elasticity_raw[i]
            )
            return_1d_score = _percentile(return_1d_raw, return_1d_raw[i])
            return_accel_score = _percentile(
                return_accel_raw, return_accel_raw[i]
            )
            range_expansion_score = _percentile(
                range_expansion_raw, range_expansion_raw[i]
            )
            close_location_score = _percentile(
                close_location_raw, close_location_raw[i]
            )
            compression = 100.0 - _percentile(
                compression_raw, compression_raw[i]
            )
            extension_risk = (
                _percentile(extension_raw, extension_raw[i]) / 100.0
            )
            liquidity_risk = (
                100.0 - _percentile(dollar_liquidity, dollar_liquidity[i])
            ) / 100.0

            direct_values = direct_by_security[row.security_id]
            premarket_turnover = direct_values["premarket_turnover"]
            volume_ignition = canonical_volume_ignition(
                rvol=rvol_score,
                float_turnover=turnover_score,
                volume_acceleration=volume_accel_score,
                premarket_turnover=premarket_turnover,
            )
            momentum_acceleration = canonical_momentum_acceleration(
                return_1d=return_1d_score,
                return_acceleration=return_accel_score,
                range_expansion=range_expansion_score,
                close_location=close_location_score,
            )

            short_ratio, dtc, si_accel, short_meta = short_by_security[row.security_id]
            si_score = (
                _percentile(short_ratio_raw, short_ratio)
                if short_ratio is not None and short_ratio_raw else None
            )
            dtc_score = (
                _percentile(dtc_raw, dtc)
                if dtc is not None and dtc_raw else None
            )
            si_accel_score = (
                _percentile(si_accel_raw, si_accel)
                if si_accel is not None and si_accel_raw else None
            )
            # Require at least one core exchange short-interest leg. Borrow/FTD
            # alone cannot manufacture ShortPressure.
            short_pressure = None
            if si_score is not None or dtc_score is not None:
                short_pressure = canonical_short_pressure(
                    si_to_float=si_score,
                    days_to_cover=dtc_score,
                    borrow_pressure=direct_values["borrow_pressure"],
                    ftd_pressure=direct_values["ftd_pressure"],
                    si_acceleration=si_accel_score,
                )

            channel_scores: dict[str, float | None] = {}
            channel_meta: dict[str, object] = {}
            social_concentration = None
            for channel in ("SOCIAL", "NEWS", "SEARCH"):
                mention_raw, author_raw, concentration, meta = (
                    channel_raw[channel][row.security_id]
                )
                mention_score = (
                    _percentile(channel_mentions[channel], mention_raw)
                    if mention_raw is not None and channel_mentions[channel]
                    else None
                )
                author_score = (
                    _percentile(channel_authors[channel], author_raw)
                    if author_raw is not None and channel_authors[channel]
                    else None
                )
                if channel == "SOCIAL":
                    social_concentration = concentration
                    channel_scores[channel] = canonical_social_velocity(
                        mention_velocity=mention_score,
                        unique_author_velocity=author_score,
                        concentration_risk=concentration,
                    )
                else:
                    channel_scores[channel] = mention_score
                channel_meta[channel] = {
                    **meta,
                    "mention_score": mention_score,
                    "unique_author_score": author_score,
                }

            social_velocity = channel_scores["SOCIAL"]
            news_velocity = channel_scores["NEWS"]
            search_velocity = channel_scores["SEARCH"]
            available_channel_velocities = [
                channel_raw[channel][row.security_id][0]
                for channel in ("SOCIAL", "NEWS", "SEARCH")
                if channel_raw[channel][row.security_id][0] is not None
            ]
            active_channels = sum(
                velocity >= 2.0 for velocity in available_channel_velocities
            )
            cross_platform = (
                100.0 * active_channels / len(available_channel_velocities)
                if available_channel_velocities else None
            )
            attention = canonical_attention(
                social_velocity=social_velocity,
                news_velocity=news_velocity,
                search_velocity=search_velocity,
                cross_platform=cross_platform,
            )

            catalyst = canonical_catalyst(
                materiality=direct_values["catalyst_materiality"],
                surprise=direct_values["catalyst_surprise"],
                credibility=direct_values["catalyst_credibility"],
                market_cap_impact=direct_values["catalyst_market_cap_impact"],
                novelty=direct_values["catalyst_novelty"],
                immediacy=direct_values["catalyst_immediacy"],
                fallback=direct_values["catalyst"],
            )

            anomaly = sum(
                sorted(
                    [turnover_score, rvol_score, momentum_acceleration or 0.0],
                    reverse=True,
                )[:2]
            ) / 2.0

            proxy_penalty = 0.20 if row.source_quality != "PIT_EXACT" else 0.0
            short_age_penalty = 0.0
            if short_meta.get("available_at"):
                short_age = (
                    as_of - datetime.fromisoformat(
                        str(short_meta["available_at"])
                    )
                ).total_seconds() / 86400.0
                short_age_penalty = min(
                    0.35, max(0.0, short_age) / 60.0 * 0.35
                )
            data_risk = min(1.0, proxy_penalty + short_age_penalty)

            features: dict[str, float | None] = {
                "market_cap_scarcity": market_cap_scarcity,
                "float_scarcity": float_scarcity,
                "short_pressure": short_pressure,
                "float_turnover": turnover_score,
                "liquidity_elasticity": liquidity_elasticity,
                "ownership_lock": direct_values["ownership_lock"],
                "catalyst": catalyst,
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
                        "PIT_MARKET_CAP"
                        if row.market_cap is not None and row.market_cap > 0
                        else "PRICE_X_FLOAT_PROXY"
                    ),
                    "float_turnover": turnover_raw[i],
                    "rvol": rvol_raw[i],
                    "volume_acceleration": volume_acceleration_raw[i],
                    "return_1d": return_1d_raw[i],
                    "return_acceleration": return_accel_raw[i],
                    "range_expansion": range_expansion_raw[i],
                    "close_location": close_location_raw[i],
                    "dollar_liquidity": dollar_liquidity[i],
                    "liquidity_elasticity": elasticity_raw[i],
                    "compression_ratio": compression_raw[i],
                    "extension_mom5": extension_raw[i],
                },
                "subscores": {
                    "rvol": rvol_score,
                    "float_turnover": turnover_score,
                    "volume_acceleration": volume_accel_score,
                    "premarket_turnover": premarket_turnover,
                    "return_1d": return_1d_score,
                    "return_acceleration": return_accel_score,
                    "range_expansion": range_expansion_score,
                    "close_location": close_location_score,
                    "search_velocity": search_velocity,
                    "cross_platform": cross_platform,
                    "social_concentration_risk": social_concentration,
                    "si_to_float": si_score,
                    "days_to_cover": dtc_score,
                    "si_acceleration": si_accel_score,
                    "borrow_pressure": direct_values["borrow_pressure"],
                    "ftd_pressure": direct_values["ftd_pressure"],
                },
                "short": short_meta,
                "attention": channel_meta,
                "direct": direct_meta_by_security[row.security_id],
                "supply_kind": row.supply_kind,
                "source_quality": row.source_quality,
            }
            snapshots.append(
                S16ReconstructedSnapshot(
                    security_id=row.security_id,
                    ticker=row.ticker,
                    as_of=row.as_of,
                    features=features,
                    evidence=evidence,
                    coverage_pct=coverage.coverage_pct,
                    missing=coverage.missing,
                    score_ready=coverage.score_ready,
                )
            )
        return snapshots

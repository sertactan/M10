from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.historical.s16_controls import S16MatchSnapshot, build_matched_controls
from core.models.s16 import S16V02Model, S16V03Model, S16V1Model
from core.models.s16_contracts import S16Input


def _input(name: str, **kw) -> S16Input:
    kw.setdefault("market_cap_scarcity", 70.0)
    return S16Input(
        security_id=name,
        ticker=name[:4].upper(),
        as_of=datetime(2025, 1, 1, tzinfo=timezone.utc),
        **kw,
    )


HARD_NEGATIVES = [
    _input("low-float-no-catalyst", float_scarcity=95, short_pressure=60, float_turnover=70, liquidity_elasticity=70, ownership_lock=85, catalyst=20, volume_ignition=20, momentum_acceleration=25, social_velocity=20, news_velocity=40, regime_sympathy=20, attention=45, compression=55, catalyst_proximity=30, theme=20, anomaly=35, dilution_risk=.2, extension_risk=.1, data_risk=.1, liquidity_risk=.3, manipulation_risk=.1),
    _input("high-si-no-volume", float_scarcity=70, short_pressure=95, float_turnover=25, liquidity_elasticity=55, ownership_lock=50, catalyst=20, volume_ignition=15, momentum_acceleration=15, social_velocity=15, news_velocity=30, regime_sympathy=25, attention=55, compression=60, catalyst_proximity=40, theme=25, anomaly=30, dilution_risk=.2, extension_risk=.1, data_risk=.1, liquidity_risk=.2, manipulation_risk=.1),
    _input("social-meme-no-squeeze", float_scarcity=60, short_pressure=35, float_turnover=55, liquidity_elasticity=60, ownership_lock=55, catalyst=30, volume_ignition=45, momentum_acceleration=90, social_velocity=70, news_velocity=55, regime_sympathy=50, attention=90, compression=50, catalyst_proximity=40, theme=50, anomaly=60, dilution_risk=.15, extension_risk=.15, data_risk=.1, liquidity_risk=.2, manipulation_risk=.1),
    _input("rvol-no-continuation", float_scarcity=55, short_pressure=40, float_turnover=95, liquidity_elasticity=75, ownership_lock=60, catalyst=35, volume_ignition=95, momentum_acceleration=55, social_velocity=80, news_velocity=45, regime_sympathy=30, attention=50, compression=65, catalyst_proximity=35, theme=30, anomaly=85, dilution_risk=.2, extension_risk=.25, data_risk=.1, liquidity_risk=.15, manipulation_risk=.1),
    _input("biotech-calendar-no-result", float_scarcity=45, short_pressure=30, float_turnover=35, liquidity_elasticity=50, ownership_lock=50, catalyst=70, volume_ignition=45, momentum_acceleration=20, social_velocity=35, news_velocity=40, regime_sympathy=55, attention=30, compression=55, catalyst_proximity=45, theme=85, anomaly=35, dilution_risk=.25, extension_risk=.1, data_risk=.1, liquidity_risk=.2, manipulation_risk=.1),
    _input("crypto-sympathy-no-filing", float_scarcity=60, short_pressure=25, float_turnover=65, liquidity_elasticity=60, ownership_lock=55, catalyst=25, volume_ignition=70, momentum_acceleration=65, social_velocity=60, news_velocity=75, regime_sympathy=30, attention=70, compression=50, catalyst_proximity=70, theme=30, anomaly=65, dilution_risk=.25, extension_risk=.1, data_risk=.1, liquidity_risk=.2, manipulation_risk=.1),
    _input("post-gap-exhausted", float_scarcity=80, short_pressure=65, float_turnover=90, liquidity_elasticity=65, ownership_lock=70, catalyst=75, volume_ignition=95, momentum_acceleration=80, social_velocity=85, news_velocity=60, regime_sympathy=60, attention=80, compression=45, catalyst_proximity=30, theme=60, anomaly=90, dilution_risk=.2, extension_risk=.9, data_risk=.1, liquidity_risk=.15, manipulation_risk=.1),
    _input("reverse-split-trap", float_scarcity=95, short_pressure=50, float_turnover=85, liquidity_elasticity=90, ownership_lock=75, catalyst=35, volume_ignition=85, momentum_acceleration=40, social_velocity=60, news_velocity=40, regime_sympathy=30, attention=45, compression=80, catalyst_proximity=35, theme=30, anomaly=80, dilution_risk=.5, extension_risk=.2, data_risk=.2, liquidity_risk=.4, manipulation_risk=.3),
    _input("dilution-overhang", float_scarcity=85, short_pressure=75, float_turnover=75, liquidity_elasticity=70, ownership_lock=65, catalyst=50, volume_ignition=80, momentum_acceleration=60, social_velocity=65, news_velocity=45, regime_sympathy=60, attention=65, compression=60, catalyst_proximity=40, theme=60, anomaly=75, dilution_risk=.95, extension_risk=.1, data_risk=.1, liquidity_risk=.2, manipulation_risk=.1),
    _input("ipo-first-day-noise", route="IPO", float_scarcity=90, short_pressure=20, float_turnover=90, liquidity_elasticity=80, ownership_lock=70, catalyst=45, volume_ignition=95, momentum_acceleration=75, social_velocity=80, news_velocity=55, regime_sympathy=50, attention=75, compression=35, catalyst_proximity=60, theme=50, anomaly=90, dilution_risk=.2, extension_risk=.2, data_risk=.3, liquidity_risk=.3, manipulation_risk=.1),
    _input("dead-cat-bounce", float_scarcity=70, short_pressure=55, float_turnover=80, liquidity_elasticity=65, ownership_lock=65, catalyst=25, volume_ignition=85, momentum_acceleration=50, social_velocity=65, news_velocity=40, regime_sympathy=20, attention=50, compression=70, catalyst_proximity=45, theme=20, anomaly=80, dilution_risk=.3, extension_risk=.5, data_risk=.1, liquidity_risk=.2, manipulation_risk=.1),
    _input("theme-runner-no-catalyst", float_scarcity=55, short_pressure=35, float_turnover=60, liquidity_elasticity=55, ownership_lock=50, catalyst=30, volume_ignition=65, momentum_acceleration=60, social_velocity=55, news_velocity=85, regime_sympathy=25, attention=65, compression=45, catalyst_proximity=85, theme=25, anomaly=70, dilution_risk=.2, extension_risk=.15, data_risk=.1, liquidity_risk=.2, manipulation_risk=.1),
]


def test_v02_false_signal_stress_baseline() -> None:
    results = [S16V02Model().analyze(x) for x in HARD_NEGATIVES]
    assert sum(x.armed_score >= 50 for x in results) == 8
    assert sum(x.armed_score >= 60 for x in results) == 0
    assert sum(x.ignition_score >= 75 for x in results) == 0


def test_v03_reduces_watch_noise_and_preserves_strong_gate() -> None:
    results = [S16V03Model().analyze(x) for x in HARD_NEGATIVES]
    assert sum(x.armed_score >= 50 for x in results) == 2
    assert sum(x.armed_score >= 60 and x.route != "IPO" for x in results) == 0
    assert sum(x.ignition_score >= 75 for x in results) == 0


def _snap(sec: str, ticker: str, d: date, k: int, *, ipo: bool = False) -> S16MatchSnapshot:
    return S16MatchSnapshot(
        security_id=sec,
        ticker=ticker,
        as_of_date=d,
        market_cap=25_000_000 * (1 + k / 200),
        float_shares=5_000_000 * (1 + k / 250),
        price=2.0 * (1 + k / 300),
        adv20=750_000 * (1 + k / 150),
        volatility20=0.08 + k / 10000,
        mom5=0.03 + k / 10000,
        mom20=0.08 + k / 8000,
        sector="TEST",
        listing_age_days=500 + k,
        ipo_route=ipo,
    )


def test_31x50_control_builder_emits_exactly_1550_without_future_labels() -> None:
    positives = []
    candidates = []
    start = date(2020, 1, 2)
    for i in range(31):
        d = start + timedelta(days=i)
        ipo = i in {15, 16, 17, 19}
        positives.append(_snap(f"P{i:02d}", f"P{i:02d}", d, 0, ipo=ipo))
        for j in range(60):
            candidates.append(_snap(f"C{i:02d}_{j:02d}", f"C{i:02d}_{j:02d}", d, j + 1, ipo=ipo))
    matches = build_matched_controls(positives, candidates, controls_per_positive=50)
    assert len(matches) == 31 * 50
    assert {m.control_rank for m in matches} == set(range(1, 51))
    assert all(m.control_security_id != m.positive_security_id for m in matches)


def test_seed_catalog_has_31_positives_and_manifest_has_1550_slots() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "data/seeds/s16_positive_events.csv").open(encoding="utf-8") as f:
        positives = list(csv.DictReader(f))
    with (root / "data/seeds/s16_matched_control_manifest.csv").open(encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))
    assert len(positives) == 31
    assert len(manifest) == 1550
    assert all(row["status"] == "PENDING_PIT_MATCH" for row in manifest)


def test_v1_canonical_rejects_hard_negative_ignition_noise() -> None:
    results = [S16V1Model().analyze(x) for x in HARD_NEGATIVES]
    non_ipo = [x for x, src in zip(results, HARD_NEGATIVES) if src.route != "IPO"]
    assert sum(x.ignition_score >= 80 for x in results) == 0
    assert sum((x.explosive_score or 0.0) >= 75 for x in non_ipo) == 0
    assert all(x.flags["CANONICAL_V1"] for x in results)


def test_v1_canonical_scores_true_explosive_archetypes_high() -> None:
    archetypes = [
        _input(
            "bio-catalyst-positive",
            market_cap_scarcity=90, float_scarcity=90, short_pressure=55,
            float_turnover=85, liquidity_elasticity=80, ownership_lock=75,
            catalyst=95, volume_ignition=95, momentum_acceleration=90,
            social_velocity=65, news_velocity=90, regime_sympathy=70,
            attention=75, compression=65, catalyst_proximity=90,
            theme=75, anomaly=90, dilution_risk=.10, extension_risk=.20,
            data_risk=.05, liquidity_risk=.15, manipulation_risk=.05,
        ),
        _input(
            "squeeze-positive",
            market_cap_scarcity=90, float_scarcity=95, short_pressure=95,
            float_turnover=95, liquidity_elasticity=90, ownership_lock=85,
            catalyst=65, volume_ignition=95, momentum_acceleration=95,
            social_velocity=95, news_velocity=75, regime_sympathy=80,
            attention=95, compression=70, catalyst_proximity=65,
            theme=80, anomaly=95, dilution_risk=.10, extension_risk=.25,
            data_risk=.05, liquidity_risk=.10, manipulation_risk=.05,
        ),
        _input(
            "treasury-positive",
            market_cap_scarcity=90, float_scarcity=85, short_pressure=45,
            float_turnover=90, liquidity_elasticity=85, ownership_lock=70,
            catalyst=95, volume_ignition=90, momentum_acceleration=85,
            social_velocity=85, news_velocity=90, regime_sympathy=90,
            attention=90, compression=60, catalyst_proximity=95,
            theme=95, anomaly=90, dilution_risk=.20, extension_risk=.15,
            data_risk=.05, liquidity_risk=.15, manipulation_risk=.05,
        ),
    ]
    results = [S16V1Model().analyze(x) for x in archetypes]
    assert all(x.flags["IGNITION_GATE"] for x in results)
    assert all(x.armed_score >= 80 for x in results)
    assert all(x.ignition_score >= 85 for x in results)
    assert all((x.explosive_score or 0.0) >= 85 for x in results)


def test_v1_market_cap_scarcity_matters_independently_of_float() -> None:
    common = dict(
        float_scarcity=90, short_pressure=70, float_turnover=75,
        liquidity_elasticity=75, ownership_lock=70, catalyst=70,
        volume_ignition=75, momentum_acceleration=70, social_velocity=70,
        news_velocity=65, regime_sympathy=65, attention=70, compression=65,
        catalyst_proximity=70, theme=65, anomaly=75, dilution_risk=.10,
        extension_risk=.10, data_risk=.05, liquidity_risk=.10,
        manipulation_risk=.05,
    )
    micro = S16V1Model().analyze(_input("micro", market_cap_scarcity=95, **common))
    large = S16V1Model().analyze(_input("large", market_cap_scarcity=10, **common))
    assert micro.fuel_score > large.fuel_score
    assert (micro.explosive_score or 0.0) > (large.explosive_score or 0.0)

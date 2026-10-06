from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from statistics import pstdev
from typing import Iterable

from core.historical.s16_controls import S16MatchSnapshot
from core.prices.models import SourcePriceBar
from data.providers.massive_pit_reference import MassivePITReference


class S16PITSnapshotUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class S16PITSnapshotEvidence:
    security_id: str
    ticker: str
    as_of_date: date
    price_source: str
    reference_source: str
    supply_kind: str
    market_cap_source: str
    sector_source: str
    price_sessions: int


def sic_sector(sic_code: str | None) -> str:
    if not sic_code:
        return ""
    digits = "".join(ch for ch in str(sic_code) if ch.isdigit())
    if not digits:
        return ""
    value = int(digits)
    if value < 1000:
        return "AGRICULTURE"
    if value < 1500:
        return "MINING"
    if value < 1800:
        return "CONSTRUCTION"
    if value < 4000:
        return "MANUFACTURING"
    if value < 5000:
        return "TRANSPORT_UTILITIES"
    if value < 5200:
        return "WHOLESALE"
    if value < 6000:
        return "RETAIL"
    if value < 6800:
        return "FINANCE_REAL_ESTATE"
    if value < 9000:
        return "SERVICES"
    return "PUBLIC_ADMIN"


def _adjusted_closes(bars: list[SourcePriceBar]) -> list[float]:
    return [float(bar.adjusted_close) for bar in bars if float(bar.adjusted_close) > 0]


def _log_returns(values: list[float]) -> list[float]:
    return [
        math.log(values[i] / values[i - 1])
        for i in range(1, len(values))
        if values[i - 1] > 0 and values[i] > 0
    ]


def build_match_snapshot(
    *,
    security_id: str,
    ticker: str,
    as_of_date: date,
    bars: Iterable[SourcePriceBar],
    reference: MassivePITReference,
    ipo_date: date | None,
    ipo_route: bool,
    free_float_shares: float | None = None,
) -> tuple[S16MatchSnapshot, S16PITSnapshotEvidence]:
    ordered = sorted(
        [bar for bar in bars if bar.trade_date <= as_of_date],
        key=lambda bar: bar.trade_date,
    )
    if len(ordered) < 21:
        raise S16PITSnapshotUnavailable(
            f"{ticker} {as_of_date}: need >=21 PIT price sessions, got {len(ordered)}"
        )
    if len({(bar.source, bar.source_symbol) for bar in ordered}) != 1:
        raise S16PITSnapshotUnavailable(
            f"{ticker} {as_of_date}: cross-provider price stitching is forbidden"
        )

    recent = ordered[-21:]
    closes = _adjusted_closes(recent)
    if len(closes) < 21:
        raise S16PITSnapshotUnavailable(
            f"{ticker} {as_of_date}: adjusted close history is incomplete"
        )

    price = closes[-1]
    adv20 = sum(float(bar.volume) for bar in recent[-20:]) / 20.0
    returns20 = _log_returns(closes[-21:])
    volatility20 = pstdev(returns20) if len(returns20) >= 2 else 0.0
    mom5 = price / closes[-6] - 1.0
    mom20 = price / closes[-21] - 1.0

    if free_float_shares is not None and free_float_shares > 0:
        supply = float(free_float_shares)
        supply_kind = "FREE_FLOAT"
    elif reference.share_class_shares_outstanding:
        supply = float(reference.share_class_shares_outstanding)
        supply_kind = "SHARE_CLASS_OUTSTANDING_PROXY"
    elif reference.weighted_shares_outstanding:
        supply = float(reference.weighted_shares_outstanding)
        supply_kind = "WEIGHTED_OUTSTANDING_PROXY"
    else:
        raise S16PITSnapshotUnavailable(
            f"{ticker} {as_of_date}: no PIT share-supply evidence"
        )

    if reference.market_cap and reference.market_cap > 0:
        market_cap = float(reference.market_cap)
        market_cap_source = "MASSIVE_PIT"
    else:
        market_cap = price * supply
        market_cap_source = "PRICE_X_PIT_SUPPLY_PROXY"

    listing_age_days = (
        max(0, (as_of_date - ipo_date).days)
        if ipo_date is not None and ipo_date <= as_of_date
        else 0
    )
    sector = sic_sector(reference.sic_code)

    snapshot = S16MatchSnapshot(
        security_id=security_id,
        ticker=ticker,
        as_of_date=as_of_date,
        market_cap=market_cap,
        float_shares=supply,
        price=price,
        adv20=adv20,
        volatility20=volatility20,
        mom5=mom5,
        mom20=mom20,
        sector=sector,
        listing_age_days=listing_age_days,
        security_type=reference.security_type or "CS",
        ipo_route=ipo_route,
        supply_kind=supply_kind,
        source_quality=(
            "PIT_EXACT"
            if supply_kind == "FREE_FLOAT" and market_cap_source == "MASSIVE_PIT"
            else "PIT_PROXY"
        ),
    )
    evidence = S16PITSnapshotEvidence(
        security_id=security_id,
        ticker=ticker,
        as_of_date=as_of_date,
        price_source=ordered[-1].source,
        reference_source=reference.source,
        supply_kind=supply_kind,
        market_cap_source=market_cap_source,
        sector_source="MASSIVE_SIC" if reference.sic_code else "MISSING",
        price_sessions=len(ordered),
    )
    return snapshot, evidence

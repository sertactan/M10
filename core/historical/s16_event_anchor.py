from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from core.prices.models import SourcePriceBar


@dataclass(frozen=True)
class S16EventAnchor:
    ticker: str
    event_period: str
    measurement_type: str
    as_of_date: date | None
    event_date: date | None
    resolution: str
    strict_5d_10x_from_prior_close: bool | None
    observed_multiple: float | None


def _adjusted_high(bar: SourcePriceBar) -> float | None:
    if bar.raw_close <= 0 or bar.adjusted_close <= 0 or bar.high <= 0:
        return None
    return float(bar.high) * float(bar.adjusted_close) / float(bar.raw_close)


def _adjusted_low(bar: SourcePriceBar) -> float | None:
    if bar.raw_close <= 0 or bar.adjusted_close <= 0 or bar.low <= 0:
        return None
    return float(bar.low) * float(bar.adjusted_close) / float(bar.raw_close)


def resolve_event_anchor(
    *,
    ticker: str,
    event_period: str,
    measurement_type: str,
    bars: Iterable[SourcePriceBar],
    threshold: float = 10.0,
    horizon_sessions: int = 5,
) -> S16EventAnchor:
    year, month = (int(x) for x in event_period.split("-", 1))
    ordered = sorted(list(bars), key=lambda b: b.trade_date)
    in_month = [
        i for i, bar in enumerate(ordered)
        if bar.trade_date.year == year and bar.trade_date.month == month
    ]
    if not in_month:
        return S16EventAnchor(
            ticker, event_period, measurement_type, None, None,
            "UNRESOLVED_NO_PRICE_IN_PERIOD", None, None,
        )

    if measurement_type == "IPO_TO_HIGH":
        first = in_month[0]
        return S16EventAnchor(
            ticker=ticker,
            event_period=event_period,
            measurement_type=measurement_type,
            as_of_date=ordered[first].trade_date,
            event_date=ordered[first].trade_date,
            resolution="IPO_FIRST_TRADE_ANCHOR",
            strict_5d_10x_from_prior_close=None,
            observed_multiple=None,
        )

    best: tuple[int, float] | None = None
    for i in in_month:
        entry = float(ordered[i].adjusted_close)
        if entry <= 0:
            continue
        future = ordered[i + 1:i + 1 + horizon_sessions]
        highs = [value for bar in future if (value := _adjusted_high(bar)) is not None]
        if not highs:
            continue
        multiple = max(highs) / entry
        if multiple >= threshold:
            best = (i, multiple)
            break

    if best is not None:
        i, multiple = best
        return S16EventAnchor(
            ticker=ticker,
            event_period=event_period,
            measurement_type=measurement_type,
            as_of_date=ordered[i].trade_date,
            event_date=ordered[i + 1].trade_date if i + 1 < len(ordered) else ordered[i].trade_date,
            resolution="STRICT_PRIOR_CLOSE_TO_5D_HIGH",
            strict_5d_10x_from_prior_close=True,
            observed_multiple=multiple,
        )

    if measurement_type == "INTRADAY_HIGH":
        for i in in_month:
            high = _adjusted_high(ordered[i])
            low = _adjusted_low(ordered[i])
            if high is None or low is None or low <= 0:
                continue
            multiple = high / low
            if multiple >= threshold:
                prior = ordered[i - 1].trade_date if i > 0 else ordered[i].trade_date
                return S16EventAnchor(
                    ticker=ticker,
                    event_period=event_period,
                    measurement_type=measurement_type,
                    as_of_date=prior,
                    event_date=ordered[i].trade_date,
                    resolution="INTRADAY_ONLY_NOT_STRICT_5D_PRIOR_CLOSE",
                    strict_5d_10x_from_prior_close=False,
                    observed_multiple=multiple,
                )

    return S16EventAnchor(
        ticker=ticker,
        event_period=event_period,
        measurement_type=measurement_type,
        as_of_date=None,
        event_date=None,
        resolution="UNRESOLVED_THRESHOLD_NOT_FOUND",
        strict_5d_10x_from_prior_close=False,
        observed_multiple=None,
    )

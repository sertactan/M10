from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RawPerSharePoint:
    period_end: str
    value: float


def exact_period_per_share_series(
    numerators: Iterable[dict],
    shares: Iterable[dict],
) -> list[RawPerSharePoint]:
    """Build conservative per-share history using exact period-end matches only.

    No weighted/basic/diluted share proxy is substituted across periods.
    """
    num_by_period: dict[str, float] = {}
    for row in numerators:
        period = str(row["period_end"])
        value = float(row["value"])
        num_by_period[period] = value

    share_by_period: dict[str, float] = {}
    for row in shares:
        period = str(row["period_end"])
        value = float(row["value"])
        if value > 0:
            share_by_period[period] = value

    out: list[RawPerSharePoint] = []
    for period in sorted(set(num_by_period) & set(share_by_period)):
        out.append(
            RawPerSharePoint(
                period_end=period,
                value=num_by_period[period] / share_by_period[period],
            )
        )
    return out


def growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior <= 0:
        return None
    return current / prior - 1.0


def cagr(current: float | None, prior: float | None, years: int) -> float | None:
    if current is None or prior is None or current <= 0 or prior <= 0 or years <= 0:
        return None
    return (current / prior) ** (1.0 / years) - 1.0


def latest_growth(points: list[RawPerSharePoint]) -> float | None:
    if len(points) < 2:
        return None
    return growth(points[-1].value, points[-2].value)


def latest_cagr(points: list[RawPerSharePoint], years: int) -> float | None:
    if len(points) < years + 1:
        return None
    return cagr(points[-1].value, points[-(years + 1)].value, years)

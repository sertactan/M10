from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from .enums import DataState, Exchange, Market


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Security:
    security_id: str
    ticker: str
    name: str
    exchange: Exchange
    market: Market = Market.US
    cik: str | None = None
    sector: str | None = None
    industry: str | None = None
    ipo_date: date | None = None
    delisted_date: date | None = None
    active: bool = True


@dataclass(frozen=True)
class DataLineage:
    provider: str
    source: str
    availability_date: datetime
    ingested_at: datetime = field(default_factory=utc_now)
    period_date: date | None = None
    filing_date: datetime | None = None
    source_url: str | None = None
    state: DataState = DataState.CACHED

    def validate(self) -> None:
        if self.availability_date.tzinfo is None:
            raise ValueError("availability_date must be timezone-aware")
        if self.ingested_at.tzinfo is None:
            raise ValueError("ingested_at must be timezone-aware")
        if self.filing_date is not None and self.filing_date.tzinfo is None:
            raise ValueError("filing_date must be timezone-aware")


@dataclass(frozen=True)
class PriceBar:
    security_id: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: float
    lineage: DataLineage
    vwap: float | None = None
    market_cap: float | None = None


@dataclass(frozen=True)
class FinancialFact:
    security_id: str
    fact_key: str
    value: float
    unit: str
    lineage: DataLineage
    fiscal_period: str | None = None
    fiscal_year: int | None = None
    raw_payload: dict[str, Any] | None = None

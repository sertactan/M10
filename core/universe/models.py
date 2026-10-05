from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from core.contracts.enums import Exchange


@dataclass(frozen=True)
class UniverseRecord:
    ticker: str
    name: str
    exchange: Exchange
    exchange_mic: str
    active: bool
    provider: str
    availability_date: datetime
    security_type: str | None = None
    cik: str | None = None
    composite_figi: str | None = None
    share_class_figi: str | None = None
    currency: str | None = "USD"
    locale: str | None = "us"
    ipo_date: date | None = None
    delisted_date: date | None = None
    provider_last_updated: datetime | None = None


@dataclass(frozen=True)
class TickerChangeEvent:
    event_date: date
    ticker: str
    provider: str
    availability_date: datetime
    event_type: str = "ticker_change"

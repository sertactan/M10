from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class PriceQualityStatus(StrEnum):
    PRIMARY = "PRIMARY"
    BOOTSTRAP = "BOOTSTRAP"
    SECONDARY = "SECONDARY"
    FALLBACK_ONLY = "FALLBACK_ONLY"
    SURVIVORSHIP_AWARE = "SURVIVORSHIP_AWARE"
    REQUIRES_ADJUSTMENT = "REQUIRES_ADJUSTMENT"
    SUSPECT = "SUSPECT"
    UNAVAILABLE = "UNAVAILABLE"


class AdjustmentStatus(StrEnum):
    DUAL_RAW_ADJUSTED = "DUAL_RAW_ADJUSTED"
    PROVIDER_ADJUSTED = "PROVIDER_ADJUSTED"
    RAW_ONLY = "RAW_ONLY"
    ADJUSTED_ONLY = "ADJUSTED_ONLY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourcePriceBar:
    security_id: str
    source: str
    source_symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    raw_close: float
    adjusted_close: float
    volume: float
    retrieved_at: datetime
    quality_status: PriceQualityStatus
    adjustment_status: AdjustmentStatus
    vwap: float | None = None
    raw_payload_hash: str | None = None


@dataclass(frozen=True)
class SplitEvent:
    security_id: str
    source: str
    source_symbol: str
    execution_date: date
    split_from: float
    split_to: float
    retrieved_at: datetime
    quality_status: PriceQualityStatus


@dataclass(frozen=True)
class DividendEvent:
    security_id: str
    source: str
    source_symbol: str
    ex_date: date
    cash_amount: float
    currency: str | None
    retrieved_at: datetime
    quality_status: PriceQualityStatus
    declaration_date: date | None = None
    record_date: date | None = None
    pay_date: date | None = None


@dataclass(frozen=True)
class MarketSnapshot:
    security_id: str
    source: str
    source_symbol: str
    as_of: datetime
    price: float | None
    day_change_pct: float | None
    volume: float | None
    retrieved_at: datetime
    quality_status: PriceQualityStatus


@dataclass(frozen=True)
class PriceSeriesDescriptor:
    security_id: str
    source: str
    source_symbol: str
    start_date: date
    end_date: date
    row_count: int
    quality_status: PriceQualityStatus
    adjustment_status: AdjustmentStatus
    retrieved_at: datetime
    content_hash: str

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class S16ShortInterestRecord:
    security_id: str
    ticker: str
    settlement_date: date
    short_interest: float
    available_at: datetime
    source: str
    source_ref: str
    quality_status: str
    avg_daily_volume: float | None = None
    float_shares: float | None = None
    days_to_cover: float | None = None


@dataclass(frozen=True)
class S16AttentionRecord:
    security_id: str
    ticker: str
    channel: str
    observed_at: datetime
    available_at: datetime
    mentions: float
    source: str
    source_ref: str
    quality_status: str
    unique_authors: float | None = None
    sentiment: float | None = None


@dataclass(frozen=True)
class S16FeatureEvidenceRecord:
    security_id: str
    ticker: str
    feature_key: str
    observed_at: datetime
    available_at: datetime
    value: float
    source: str
    source_ref: str
    quality_status: str

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class FundamentalQualityStatus(StrEnum):
    AUTHORITATIVE = "AUTHORITATIVE"
    SECONDARY = "SECONDARY"
    BOOTSTRAP = "BOOTSTRAP"
    FALLBACK = "FALLBACK"
    OFFICIAL_IR = "OFFICIAL_IR"
    SUSPECT = "SUSPECT"


class FundamentalValidationStatus(StrEnum):
    SEC_CANONICAL = "SEC_CANONICAL"
    NOT_CHECKED = "NOT_CHECKED"
    MATCH = "MATCH"
    CLOSE = "CLOSE"
    MISMATCH = "MISMATCH"
    CONFLICT = "CONFLICT"
    ESTIMATE_ONLY = "ESTIMATE_ONLY"
    GUIDANCE_ONLY = "GUIDANCE_ONLY"


class FactFamily(StrEnum):
    REGULATORY = "REGULATORY"
    NORMALIZED = "NORMALIZED"
    COMPANY_METRIC = "COMPANY_METRIC"
    ESTIMATE = "ESTIMATE"
    GUIDANCE = "GUIDANCE"


class PeriodKind(StrEnum):
    INSTANT = "INSTANT"
    QUARTER = "QUARTER"
    YTD = "YTD"
    ANNUAL = "ANNUAL"
    OTHER = "OTHER"


@dataclass(frozen=True)
class FilingRecord:
    security_id: str
    source: str
    cik: str | None
    form_type: str
    filing_date: date
    accepted_at: datetime | None
    accession_number: str | None
    source_document: str | None
    retrieved_at: datetime
    period_end: date | None = None
    primary_document: str | None = None
    is_amendment: bool = False


@dataclass(frozen=True)
class FundamentalFactRow:
    security_id: str
    metric_name: str
    provider_metric_name: str
    value: float
    unit: str
    period_end: date
    filing_date: date | None
    accepted_at: datetime | None
    available_at: datetime
    source: str
    source_document: str
    accession_number: str | None
    retrieved_at: datetime
    quality_status: FundamentalQualityStatus
    validation_status: FundamentalValidationStatus
    family: FactFamily
    period_kind: PeriodKind
    period_start: date | None = None
    form_type: str | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    taxonomy: str | None = None
    frame: str | None = None
    statement_type: str | None = None
    is_amendment: bool = False
    raw_payload_hash: str | None = None


@dataclass(frozen=True)
class EstimateRow:
    security_id: str
    metric_name: str
    period_end: date
    value: float
    source: str
    source_document: str
    retrieved_at: datetime
    available_at: datetime
    quality_status: FundamentalQualityStatus
    validation_status: FundamentalValidationStatus
    unit: str | None = None
    low: float | None = None
    high: float | None = None
    analyst_count: int | None = None


@dataclass(frozen=True)
class GuidanceKPI:
    security_id: str
    metric_name: str
    source: str
    source_document: str
    retrieved_at: datetime
    available_at: datetime
    quality_status: FundamentalQualityStatus
    validation_status: FundamentalValidationStatus
    period_end: date | None = None
    value: float | None = None
    value_low: float | None = None
    value_high: float | None = None
    unit: str | None = None
    text_value: str | None = None
    accession_number: str | None = None

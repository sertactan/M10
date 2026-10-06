from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from core.historical.s16_evidence import (
    S16AttentionRecord,
    S16FeatureEvidenceRecord,
    S16ShortInterestRecord,
)


DIRECT_FEATURE_KEYS = {
    # Canonical direct V1 inputs.
    "ownership_lock",
    "catalyst",
    "regime_sympathy",
    "catalyst_proximity",
    "theme",
    "dilution_risk",
    "manipulation_risk",

    # Short-pressure sublegs (0..100).
    "borrow_pressure",
    "ftd_pressure",

    # Optional premarket subleg (0..100).
    "premarket_turnover",

    # Catalyst sublegs (0..100).
    "catalyst_materiality",
    "catalyst_surprise",
    "catalyst_credibility",
    "catalyst_market_cap_impact",
    "catalyst_novelty",
    "catalyst_immediacy",
}


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _number(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def read_short_interest_csv(
    path: str | Path,
    *,
    resolve_security_id,
) -> list[S16ShortInterestRecord]:
    out: list[S16ShortInterestRecord] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            settlement = date.fromisoformat(raw["settlement_date"])
            ticker = raw["ticker"].strip().upper()
            security_id = resolve_security_id(ticker, settlement)
            if not security_id:
                continue
            out.append(S16ShortInterestRecord(
                security_id=security_id,
                ticker=ticker,
                settlement_date=settlement,
                short_interest=float(raw["short_interest"]),
                avg_daily_volume=_number(raw.get("avg_daily_volume")),
                float_shares=_number(raw.get("float_shares")),
                days_to_cover=_number(raw.get("days_to_cover")),
                available_at=_dt(raw["available_at"]),
                source=raw["source"].strip(),
                source_ref=raw["source_ref"].strip(),
                quality_status=(raw.get("quality_status") or "ARCHIVE").strip(),
            ))
    return out


def read_attention_csv(
    path: str | Path,
    *,
    resolve_security_id,
) -> list[S16AttentionRecord]:
    out: list[S16AttentionRecord] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            observed = _dt(raw["observed_at"])
            ticker = raw["ticker"].strip().upper()
            security_id = resolve_security_id(ticker, observed.date())
            if not security_id:
                continue
            out.append(S16AttentionRecord(
                security_id=security_id,
                ticker=ticker,
                channel=raw["channel"].strip().upper(),
                observed_at=observed,
                available_at=_dt(raw["available_at"]),
                mentions=float(raw["mentions"]),
                unique_authors=_number(raw.get("unique_authors")),
                sentiment=_number(raw.get("sentiment")),
                source=raw["source"].strip(),
                source_ref=raw["source_ref"].strip(),
                quality_status=(raw.get("quality_status") or "ARCHIVE").strip(),
            ))
    return out


def read_feature_evidence_csv(
    path: str | Path,
    *,
    resolve_security_id,
) -> list[S16FeatureEvidenceRecord]:
    out: list[S16FeatureEvidenceRecord] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            feature_key = raw["feature_key"].strip()
            if feature_key not in DIRECT_FEATURE_KEYS:
                raise ValueError(f"unsupported direct S16 feature: {feature_key}")
            observed = _dt(raw["observed_at"])
            ticker = raw["ticker"].strip().upper()
            security_id = resolve_security_id(ticker, observed.date())
            if not security_id:
                continue
            value = float(raw["value"])
            if feature_key.endswith("_risk"):
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"{feature_key} must be in [0,1]")
            elif not 0.0 <= value <= 100.0:
                raise ValueError(f"{feature_key} must be in [0,100]")
            out.append(S16FeatureEvidenceRecord(
                security_id=security_id,
                ticker=ticker,
                feature_key=feature_key,
                observed_at=observed,
                available_at=_dt(raw["available_at"]),
                value=value,
                source=raw["source"].strip(),
                source_ref=raw["source_ref"].strip(),
                quality_status=(raw.get("quality_status") or "ARCHIVE").strip(),
            ))
    return out

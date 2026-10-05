from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from core.contracts.entities import Security
from core.fundamentals.metrics import canonical_metric, classify_period
from core.fundamentals.models import (
    EstimateRow,
    FactFamily,
    FilingRecord,
    FundamentalFactRow,
    FundamentalQualityStatus,
    FundamentalValidationStatus,
    GuidanceKPI,
    PeriodKind,
)
from data.providers.http_json import JsonHttpClient
from data.providers.price_utils import sha256_payload


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class FinnhubFundamentalsProvider:
    name = "FINNHUB"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://finnhub.io/api/v1",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.http = JsonHttpClient(timeout_seconds, max_retries)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _key(self) -> str:
        if not self.api_key:
            raise RuntimeError("FINNHUB_API_KEY is not configured")
        return self.api_key

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        return await self.http.get_json(
            f"{self.base_url}/{path.lstrip('/')}",
            params={**params, "token": self._key()},
        )

    async def get_filings(self, security: Security) -> list[FilingRecord]:
        return []

    async def get_facts(self, security: Security) -> list[FundamentalFactRow]:
        payload = await self._get(
            "/stock/financials-reported",
            {"symbol": security.ticker, "freq": "quarterly"},
        )
        return self.parse_reported_financials(
            security.security_id,
            security.ticker,
            payload,
            retrieved_at=_now(),
            source_document=f"{self.base_url}/stock/financials-reported",
        )

    @staticmethod
    def parse_reported_financials(
        security_id: str,
        ticker: str,
        payload: dict[str, Any],
        *,
        retrieved_at: datetime,
        source_document: str,
    ) -> list[FundamentalFactRow]:
        out: list[FundamentalFactRow] = []
        for report in payload.get("data") or []:
            filed = _date(report.get("filedDate"))
            end = _date(report.get("endDate"))
            start = _date(report.get("startDate"))
            if filed is None or end is None:
                continue
            available_at = datetime.combine(
                filed + timedelta(days=1), time.min, tzinfo=timezone.utc
            )
            form = str(report.get("form") or "").strip() or None
            accession = str(report.get("accessNumber") or "").strip() or None
            for statement_type in ("bs", "ic", "cf"):
                for item in (report.get("report") or {}).get(statement_type) or []:
                    concept = str(item.get("concept") or item.get("label") or "").strip()
                    value = item.get("value")
                    if not concept or not isinstance(value, (int, float)):
                        continue
                    unit = str(item.get("unit") or "").strip() or "UNKNOWN"
                    metric = canonical_metric("us-gaap", concept)
                    out.append(FundamentalFactRow(
                        security_id=security_id,
                        metric_name=metric,
                        provider_metric_name=concept,
                        value=float(value),
                        unit=unit,
                        period_start=start,
                        period_end=end,
                        period_kind=PeriodKind(classify_period(start, end)),
                        filing_date=filed,
                        accepted_at=None,
                        available_at=available_at,
                        source="FINNHUB",
                        source_document=source_document,
                        accession_number=accession,
                        retrieved_at=retrieved_at,
                        quality_status=FundamentalQualityStatus.SECONDARY,
                        validation_status=FundamentalValidationStatus.NOT_CHECKED,
                        family=FactFamily.NORMALIZED,
                        form_type=form,
                        fiscal_year=int(report["year"]) if report.get("year") else None,
                        fiscal_period=str(report.get("quarter")) if report.get("quarter") else None,
                        taxonomy="us-gaap",
                        statement_type=statement_type.upper(),
                        is_amendment=bool(form and form.endswith("/A")),
                        raw_payload_hash=sha256_payload(item),
                    ))
        return out

    async def get_estimates(self, security: Security) -> list[EstimateRow]:
        now = _now()
        out: list[EstimateRow] = []
        for endpoint, metric, unit in (
            ("stock/revenue-estimate", "REVENUE_ESTIMATE", "USD"),
            ("stock/eps-estimate", "EPS_ESTIMATE", "USD/share"),
        ):
            try:
                payload = await self._get(endpoint, {"symbol": security.ticker, "freq": "quarterly"})
            except Exception:
                continue
            out.extend(
                self.parse_estimates(
                    security.security_id,
                    payload,
                    metric_name=metric,
                    unit=unit,
                    source_document=f"{self.base_url}/{endpoint}",
                    retrieved_at=now,
                )
            )
        return out

    @staticmethod
    def parse_estimates(
        security_id: str,
        payload: dict[str, Any],
        *,
        metric_name: str,
        unit: str,
        source_document: str,
        retrieved_at: datetime,
    ) -> list[EstimateRow]:
        out: list[EstimateRow] = []
        for item in payload.get("data") or []:
            period = _date(item.get("period"))
            avg = item.get("avg")
            if period is None or not isinstance(avg, (int, float)):
                continue
            count = item.get("numberAnalysts")
            out.append(EstimateRow(
                security_id=security_id,
                metric_name=metric_name,
                period_end=period,
                value=float(avg),
                unit=unit,
                low=float(item["low"]) if isinstance(item.get("low"), (int, float)) else None,
                high=float(item["high"]) if isinstance(item.get("high"), (int, float)) else None,
                analyst_count=int(count) if isinstance(count, (int, float)) else None,
                source="FINNHUB",
                source_document=source_document,
                retrieved_at=retrieved_at,
                available_at=retrieved_at,
                quality_status=FundamentalQualityStatus.SECONDARY,
                validation_status=FundamentalValidationStatus.ESTIMATE_ONLY,
            ))
        return out

    async def get_company_metrics(self, security: Security) -> list[GuidanceKPI]:
        payload = await self._get(
            "/stock/metric", {"symbol": security.ticker, "metric": "all"}
        )
        now = _now()
        out: list[GuidanceKPI] = []
        for key, value in (payload.get("metric") or {}).items():
            if not isinstance(value, (int, float)):
                continue
            out.append(GuidanceKPI(
                security_id=security.security_id,
                metric_name=f"FINNHUB_METRIC:{key}",
                value=float(value),
                source="FINNHUB",
                source_document=f"{self.base_url}/stock/metric",
                retrieved_at=now,
                available_at=now,
                quality_status=FundamentalQualityStatus.SECONDARY,
                validation_status=FundamentalValidationStatus.NOT_CHECKED,
            ))
        return out

    async def validate_symbol(self, security: Security) -> bool:
        try:
            payload = await self._get("/stock/profile2", {"symbol": security.ticker})
            return bool(payload.get("ticker"))
        except Exception:
            return False

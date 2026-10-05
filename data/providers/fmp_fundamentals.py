from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from core.contracts.entities import Security
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


FMP_METRIC_MAP = {
    "revenue": "REVENUE",
    "netIncome": "NET_INCOME",
    "grossProfit": "GROSS_PROFIT",
    "operatingIncome": "OPERATING_INCOME",
    "operatingCashFlow": "OPERATING_CASH_FLOW",
    "capitalExpenditure": "CAPEX",
    "cashAndShortTermInvestments": "CASH",
    "totalAssets": "ASSETS",
    "totalLiabilities": "LIABILITIES",
    "totalStockholdersEquity": "EQUITY",
    "weightedAverageShsOutDil": "SHARES_OUTSTANDING",
    "epsdiluted": "DILUTED_EPS",
    "researchAndDevelopmentExpenses": "R_AND_D",
    "sellingGeneralAndAdministrativeExpenses": "SG_AND_A",
    "stockBasedCompensation": "SBC",
}


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


class FMPFundamentalsProvider:
    name = "FMP"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://financialmodelingprep.com/stable",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.http = JsonHttpClient(timeout_seconds, max_retries)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def _get(self, endpoint: str, symbol: str) -> Any:
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is not configured")
        return await self.http.get_json(
            f"{self.base_url}/{endpoint}",
            params={"symbol": symbol, "apikey": self.api_key},
        )

    async def get_filings(self, security: Security) -> list[FilingRecord]:
        return []

    async def get_facts(self, security: Security) -> list[FundamentalFactRow]:
        now = datetime.now(timezone.utc)
        out: list[FundamentalFactRow] = []
        for endpoint, statement_type in (
            ("income-statement", "INCOME"),
            ("balance-sheet-statement", "BALANCE"),
            ("cash-flow-statement", "CASH_FLOW"),
        ):
            try:
                payload = await self._get(endpoint, security.ticker)
            except Exception:
                continue
            if not isinstance(payload, list):
                continue
            out.extend(self.parse_statements(
                security.security_id,
                payload,
                statement_type=statement_type,
                retrieved_at=now,
                source_document=f"{self.base_url}/{endpoint}",
            ))
        return out

    @staticmethod
    def parse_statements(
        security_id: str,
        rows: list[dict[str, Any]],
        *,
        statement_type: str,
        retrieved_at: datetime,
        source_document: str,
    ) -> list[FundamentalFactRow]:
        out: list[FundamentalFactRow] = []
        for row in rows:
            period_end = _parse_date(row.get("date"))
            filed = _parse_date(row.get("fillingDate") or row.get("filingDate"))
            if period_end is None:
                continue
            accepted = _parse_dt(row.get("acceptedDate"))
            if accepted:
                available = accepted
            elif filed:
                available = datetime.combine(
                    filed + timedelta(days=1), time.min, tzinfo=timezone.utc
                )
            else:
                available = retrieved_at
            period = str(row.get("period") or "").upper()
            kind = PeriodKind.ANNUAL if period in {"FY", "ANNUAL"} else PeriodKind.QUARTER
            for provider_key, canonical in FMP_METRIC_MAP.items():
                value = row.get(provider_key)
                if not isinstance(value, (int, float)):
                    continue
                unit = "USD/share" if "eps" in provider_key.lower() else (
                    "shares" if "shsout" in provider_key.lower() else "USD"
                )
                out.append(FundamentalFactRow(
                    security_id=security_id,
                    metric_name=canonical,
                    provider_metric_name=provider_key,
                    value=float(value),
                    unit=unit,
                    period_end=period_end,
                    period_kind=kind,
                    filing_date=filed,
                    accepted_at=accepted,
                    available_at=available,
                    source="FMP",
                    source_document=source_document,
                    accession_number=None,
                    retrieved_at=retrieved_at,
                    quality_status=FundamentalQualityStatus.FALLBACK,
                    validation_status=FundamentalValidationStatus.NOT_CHECKED,
                    family=FactFamily.NORMALIZED,
                    form_type=str(row.get("form")) if row.get("form") else None,
                    fiscal_year=int(row["calendarYear"]) if str(row.get("calendarYear") or "").isdigit() else None,
                    fiscal_period=period or None,
                    statement_type=statement_type,
                    raw_payload_hash=sha256_payload(row),
                ))
        return out

    async def get_estimates(self, security: Security) -> list[EstimateRow]:
        return []

    async def get_company_metrics(self, security: Security) -> list[GuidanceKPI]:
        now = datetime.now(timezone.utc)
        try:
            payload = await self._get("ratios", security.ticker)
        except Exception:
            return []
        rows = payload if isinstance(payload, list) else []
        if not rows:
            return []
        latest = rows[0]
        out: list[GuidanceKPI] = []
        for key, value in latest.items():
            if not isinstance(value, (int, float)):
                continue
            out.append(GuidanceKPI(
                security_id=security.security_id,
                metric_name=f"FMP_RATIO:{key}",
                value=float(value),
                source="FMP",
                source_document=f"{self.base_url}/ratios",
                retrieved_at=now,
                available_at=now,
                quality_status=FundamentalQualityStatus.FALLBACK,
                validation_status=FundamentalValidationStatus.NOT_CHECKED,
            ))
        return out

    async def validate_symbol(self, security: Security) -> bool:
        if not self.configured:
            return False
        try:
            payload = await self._get("profile", security.ticker)
            return bool(payload)
        except Exception:
            return False

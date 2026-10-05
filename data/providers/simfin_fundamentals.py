from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path

import pandas as pd

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
from data.providers.price_utils import sha256_payload


COLUMN_METRICS = {
    "Revenue": "REVENUE",
    "Net Income": "NET_INCOME",
    "Gross Profit": "GROSS_PROFIT",
    "Operating Income (Loss)": "OPERATING_INCOME",
    "Net Cash from Operating Activities": "OPERATING_CASH_FLOW",
    "Capital Expenditures": "CAPEX",
    "Cash, Cash Equivalents & Short Term Investments": "CASH",
    "Total Assets": "ASSETS",
    "Total Liabilities": "LIABILITIES",
    "Total Equity": "EQUITY",
    "Shares (Diluted)": "SHARES_OUTSTANDING",
    "EPS, Diluted": "DILUTED_EPS",
}


def _find(frame: pd.DataFrame, *names: str) -> str | None:
    lowered = {str(c).strip().lower(): str(c) for c in frame.columns}
    for n in names:
        hit = lowered.get(n.lower())
        if hit:
            return hit
    return None


class SimFinFundamentalsProvider:
    name = "SIMFIN"

    def __init__(self, bulk_path: str | Path | None = None) -> None:
        self.bulk_path = Path(bulk_path) if bulk_path else None

    @property
    def configured(self) -> bool:
        return self.bulk_path is not None and self.bulk_path.exists()

    def _files(self) -> list[Path]:
        if not self.configured:
            return []
        assert self.bulk_path is not None
        if self.bulk_path.is_file():
            return [self.bulk_path]
        return sorted(
            [p for p in self.bulk_path.rglob("*") if p.suffix.lower() in {".csv", ".zip"}]
        )

    async def get_filings(self, security: Security) -> list[FilingRecord]:
        return []

    async def get_facts(self, security: Security) -> list[FundamentalFactRow]:
        if not self.configured:
            raise RuntimeError("SIMFIN_FUNDAMENTALS_PATH is not configured")
        out: list[FundamentalFactRow] = []
        now = datetime.now(timezone.utc)
        for path in self._files():
            compression = "zip" if path.suffix.lower() == ".zip" else "infer"
            for chunk in pd.read_csv(path, compression=compression, chunksize=100_000):
                ticker_col = _find(chunk, "Ticker")
                if not ticker_col:
                    continue
                subset = chunk[chunk[ticker_col].astype(str).str.upper() == security.ticker.upper()]
                if subset.empty:
                    continue
                out.extend(self.parse_frame(
                    security.security_id,
                    subset.copy(),
                    retrieved_at=now,
                    source_document=str(path),
                ))
        return out

    @staticmethod
    def parse_frame(
        security_id: str,
        frame: pd.DataFrame,
        *,
        retrieved_at: datetime,
        source_document: str,
    ) -> list[FundamentalFactRow]:
        report_col = _find(frame, "Report Date")
        publish_col = _find(frame, "Publish Date")
        fy_col = _find(frame, "Fiscal Year")
        fp_col = _find(frame, "Fiscal Period")
        if not report_col or not publish_col:
            return []
        out: list[FundamentalFactRow] = []
        for _, row in frame.iterrows():
            period_end = pd.to_datetime(row[report_col]).date()
            publish_date = pd.to_datetime(row[publish_col]).date()
            available_at = datetime.combine(publish_date, time.min, tzinfo=timezone.utc)
            fiscal_period = str(row[fp_col]) if fp_col and pd.notna(row[fp_col]) else None
            kind = PeriodKind.ANNUAL if fiscal_period in {"FY", "TTM"} else PeriodKind.QUARTER
            for col, metric in COLUMN_METRICS.items():
                if col not in frame.columns or pd.isna(row[col]):
                    continue
                value = row[col]
                if not isinstance(value, (int, float)):
                    try:
                        value = float(value)
                    except Exception:
                        continue
                unit = "USD/share" if "EPS" in col else ("shares" if "Shares" in col else "USD")
                out.append(FundamentalFactRow(
                    security_id=security_id,
                    metric_name=metric,
                    provider_metric_name=col,
                    value=float(value),
                    unit=unit,
                    period_start=None,
                    period_end=period_end,
                    period_kind=kind,
                    filing_date=publish_date,
                    accepted_at=None,
                    available_at=available_at,
                    source="SIMFIN",
                    source_document=source_document,
                    accession_number=None,
                    retrieved_at=retrieved_at,
                    quality_status=FundamentalQualityStatus.BOOTSTRAP,
                    validation_status=FundamentalValidationStatus.NOT_CHECKED,
                    family=FactFamily.NORMALIZED,
                    fiscal_year=int(row[fy_col]) if fy_col and pd.notna(row[fy_col]) else None,
                    fiscal_period=fiscal_period,
                    raw_payload_hash=sha256_payload(row.to_dict()),
                ))
        return out

    async def get_estimates(self, security: Security) -> list[EstimateRow]:
        return []

    async def get_company_metrics(self, security: Security) -> list[GuidanceKPI]:
        return []

    async def validate_symbol(self, security: Security) -> bool:
        if not self.configured:
            return False
        try:
            for path in self._files():
                compression = "zip" if path.suffix.lower() == ".zip" else "infer"
                frame = pd.read_csv(path, compression=compression, nrows=50000)
                ticker_col = _find(frame, "Ticker")
                if ticker_col and security.ticker.upper() in set(frame[ticker_col].astype(str).str.upper()):
                    return True
        except Exception:
            return False
        return False

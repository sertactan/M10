from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlparse

from core.contracts.entities import Security
from core.fundamentals.models import (
    FundamentalQualityStatus,
    FundamentalValidationStatus,
    GuidanceKPI,
)


class CompanyInvestorRelationsProvider:
    name = "COMPANY_IR"

    @staticmethod
    def _require_official_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Investor Relations source_document must be an HTTPS official document URL")

    def ingest_structured(
        self,
        security: Security,
        records: list[dict],
        *,
        retrieved_at: datetime,
    ) -> list[GuidanceKPI]:
        out: list[GuidanceKPI] = []
        for row in records:
            source_document = str(row.get("source_document") or "").strip()
            self._require_official_url(source_document)
            source = str(row.get("source") or self.name).strip().upper()
            if source not in {"COMPANY_IR", "SEC_EDGAR"}:
                raise ValueError("Structured KPI source must be COMPANY_IR or SEC_EDGAR")
            if source == "SEC_EDGAR":
                host = (urlparse(source_document).hostname or "").lower()
                if not (host == "sec.gov" or host.endswith(".sec.gov")):
                    raise ValueError("SEC_EDGAR structured KPI must reference an official sec.gov document")
                if not row.get("accession_number"):
                    raise ValueError("SEC_EDGAR structured KPI requires accession_number")
            metric_name = str(row.get("metric_name") or "").strip()
            if not metric_name:
                raise ValueError("IR record requires metric_name")
            available_at = row.get("available_at")
            if isinstance(available_at, str):
                available_at = datetime.fromisoformat(available_at.replace("Z", "+00:00"))
            if not isinstance(available_at, datetime) or available_at.tzinfo is None:
                raise ValueError("IR record requires timezone-aware available_at")
            period_end = row.get("period_end")
            if isinstance(period_end, str) and period_end:
                period_end = date.fromisoformat(period_end)
            out.append(GuidanceKPI(
                security_id=security.security_id,
                metric_name=metric_name,
                period_end=period_end if isinstance(period_end, date) else None,
                value=float(row["value"]) if isinstance(row.get("value"), (int, float)) else None,
                value_low=float(row["value_low"]) if isinstance(row.get("value_low"), (int, float)) else None,
                value_high=float(row["value_high"]) if isinstance(row.get("value_high"), (int, float)) else None,
                unit=str(row.get("unit")) if row.get("unit") else None,
                text_value=str(row.get("text_value")) if row.get("text_value") else None,
                source=source,
                source_document=source_document,
                accession_number=str(row.get("accession_number")) if row.get("accession_number") else None,
                retrieved_at=retrieved_at,
                available_at=available_at,
                quality_status=(
                    FundamentalQualityStatus.AUTHORITATIVE
                    if source == "SEC_EDGAR"
                    else FundamentalQualityStatus.OFFICIAL_IR
                ),
                validation_status=(
                    FundamentalValidationStatus.SEC_CANONICAL
                    if source == "SEC_EDGAR"
                    else FundamentalValidationStatus.GUIDANCE_ONLY
                ),
            ))
        return out

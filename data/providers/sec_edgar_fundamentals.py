from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
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
from data.cache.sec_json_mirror import SecJsonMirror
from data.providers.http_json import JsonHttpClient
from data.providers.sec_access import resolve_sec_user_agent
from data.providers.price_utils import sha256_payload


FACT_FORMS = {
    "10-K", "10-K/A",
    "10-Q", "10-Q/A",
    "8-K", "8-K/A",
    "20-F", "20-F/A",
    "40-F", "40-F/A",
    "6-K", "6-K/A",
}

# Filing-history coverage is intentionally broader than XBRL-fact coverage.
# S16 needs financing / offering forms for PIT dilution-risk evidence, but those
# forms must never be treated as canonical financial-statement facts.
S16_EVENT_FORMS = {
    "S-1", "S-1/A", "S-3", "S-3/A",
    "F-1", "F-1/A", "F-3", "F-3/A",
    "424B2", "424B3", "424B4", "424B5",
    "EFFECT", "RW",
    "DEF 14A", "PRE 14A",
}

SUPPORTED_FORMS = FACT_FORMS | S16_EVENT_FORMS


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 14:
        # Legacy EDGAR headers are Eastern time. Conservatively store as UTC-5;
        # this never makes a fact available earlier than the true instant during DST.
        parsed = datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
        return parsed.replace(tzinfo=timezone(timedelta(hours=-5))).astimezone(timezone.utc)
    return None


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class SECEdgarFundamentalsProvider:
    name = "SEC_EDGAR"

    def __init__(
        self,
        *,
        data_base_url: str = "https://data.sec.gov",
        archive_base_url: str = "https://www.sec.gov/Archives/edgar/data",
        user_agent: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        mirror_root: str | Path | None = None,
    ) -> None:
        self.data_base_url = data_base_url.rstrip("/")
        self.archive_base_url = archive_base_url.rstrip("/")
        self.user_agent = resolve_sec_user_agent(user_agent)
        self.http = JsonHttpClient(timeout_seconds, max_retries)
        self.mirror = SecJsonMirror(mirror_root) if mirror_root is not None else None
        self._filing_cache: dict[str, list[FilingRecord]] = {}

    @property
    def configured(self) -> bool:
        return True

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    async def _get_json(self, url: str) -> Any:
        if self.mirror is not None:
            return (await self.mirror.fetch_json(self.http, url, headers=self._headers())).payload
        return await self.http.get_json(url, headers=self._headers())

    @staticmethod
    def _cik(security: Security) -> str:
        if not security.cik:
            raise RuntimeError(f"CIK missing for {security.ticker}")
        digits = "".join(ch for ch in str(security.cik) if ch.isdigit())
        return digits.zfill(10)

    async def get_filings(self, security: Security) -> list[FilingRecord]:
        cik = self._cik(security)
        if cik in self._filing_cache:
            return self._filing_cache[cik]

        payload = await self._get_json(
            f"{self.data_base_url}/submissions/CIK{cik}.json"
        )
        out = self.parse_submissions_payload(
            security.security_id,
            cik,
            payload,
            retrieved_at=_utc_now(),
            archive_base_url=self.archive_base_url,
        )

        files = ((payload.get("filings") or {}).get("files") or [])
        for item in files:
            name = item.get("name")
            if not name:
                continue
            additional = await self._get_json(
                f"{self.data_base_url}/submissions/{name}"
            )
            out.extend(
                self.parse_submissions_payload(
                    security.security_id,
                    cik,
                    additional,
                    retrieved_at=_utc_now(),
                    archive_base_url=self.archive_base_url,
                )
            )

        dedup: dict[str, FilingRecord] = {}
        for filing in out:
            key = filing.accession_number or (
                f"{filing.form_type}|{filing.filing_date}|{filing.source_document}"
            )
            dedup[key] = filing
        result = sorted(
            dedup.values(),
            key=lambda f: (
                f.accepted_at or datetime.combine(f.filing_date, time.max, tzinfo=timezone.utc),
                f.accession_number or "",
            ),
        )
        self._filing_cache[cik] = result
        return result

    @classmethod
    def parse_submissions_payload(
        cls,
        security_id: str,
        cik: str,
        payload: dict[str, Any],
        *,
        retrieved_at: datetime,
        archive_base_url: str = "https://www.sec.gov/Archives/edgar/data",
    ) -> list[FilingRecord]:
        block = payload
        if "filings" in payload:
            block = (payload.get("filings") or {}).get("recent") or {}

        columns = {
            key: value
            for key, value in block.items()
            if isinstance(value, list)
        }
        if not columns:
            return []
        n = max((len(v) for v in columns.values()), default=0)

        out: list[FilingRecord] = []
        cik_int = str(int(cik))
        for i in range(n):
            def cell(name: str):
                values = columns.get(name) or []
                return values[i] if i < len(values) else None

            form = str(cell("form") or "").strip()
            if form not in SUPPORTED_FORMS:
                continue
            filing_date = _parse_date(cell("filingDate"))
            if filing_date is None:
                continue
            accession = str(cell("accessionNumber") or "").strip() or None
            primary_document = str(cell("primaryDocument") or "").strip() or None
            source_document = None
            if accession and primary_document:
                source_document = (
                    f"{archive_base_url}/{cik_int}/"
                    f"{accession.replace('-', '')}/{primary_document}"
                )
            accepted_at = _parse_datetime(cell("acceptanceDateTime"))
            out.append(
                FilingRecord(
                    security_id=security_id,
                    source="SEC_EDGAR",
                    cik=cik,
                    form_type=form,
                    filing_date=filing_date,
                    accepted_at=accepted_at,
                    accession_number=accession,
                    source_document=source_document,
                    primary_document=primary_document,
                    period_end=_parse_date(cell("reportDate")),
                    retrieved_at=retrieved_at,
                    is_amendment=form.endswith("/A"),
                )
            )
        return out

    async def get_facts(self, security: Security) -> list[FundamentalFactRow]:
        cik = self._cik(security)
        filings = await self.get_filings(security)
        filing_map = {
            f.accession_number: f
            for f in filings
            if f.accession_number
        }
        payload = await self._get_json(
            f"{self.data_base_url}/api/xbrl/companyfacts/CIK{cik}.json"
        )
        return self.parse_companyfacts_payload(
            security.security_id,
            cik,
            payload,
            filing_map=filing_map,
            retrieved_at=_utc_now(),
            companyfacts_url=f"{self.data_base_url}/api/xbrl/companyfacts/CIK{cik}.json",
        )

    @staticmethod
    def parse_companyfacts_payload(
        security_id: str,
        cik: str,
        payload: dict[str, Any],
        *,
        filing_map: dict[str, FilingRecord],
        retrieved_at: datetime,
        companyfacts_url: str,
    ) -> list[FundamentalFactRow]:
        out: list[FundamentalFactRow] = []
        facts = payload.get("facts") or {}
        for taxonomy, taxonomy_facts in facts.items():
            if not isinstance(taxonomy_facts, dict):
                continue
            for tag, concept in taxonomy_facts.items():
                units = (concept or {}).get("units") or {}
                for unit, items in units.items():
                    for item in items or []:
                        form = str(item.get("form") or "").strip()
                        if form not in SUPPORTED_FORMS:
                            continue
                        end = _parse_date(item.get("end"))
                        if end is None:
                            continue
                        value = item.get("val")
                        if not isinstance(value, (int, float)):
                            continue
                        accession = str(item.get("accn") or "").strip() or None
                        filing = filing_map.get(accession)
                        filed = (
                            filing.filing_date
                            if filing
                            else _parse_date(item.get("filed"))
                        )
                        if filed is None:
                            continue
                        accepted_at = filing.accepted_at if filing else None
                        if accepted_at is not None:
                            available_at = accepted_at
                        else:
                            # Fail-conservative when old metadata lacks an acceptance time.
                            available_at = datetime.combine(
                                filed + timedelta(days=1),
                                time.min,
                                tzinfo=timezone.utc,
                            )
                        start = _parse_date(item.get("start"))
                        kind = PeriodKind(classify_period(start, end))
                        source_document = (
                            filing.source_document
                            if filing and filing.source_document
                            else companyfacts_url
                        )
                        metric = canonical_metric(str(taxonomy), str(tag))
                        out.append(
                            FundamentalFactRow(
                                security_id=security_id,
                                metric_name=metric,
                                provider_metric_name=str(tag),
                                value=float(value),
                                unit=str(unit),
                                period_start=start,
                                period_end=end,
                                filing_date=filed,
                                accepted_at=accepted_at,
                                available_at=available_at,
                                source="SEC_EDGAR",
                                source_document=source_document,
                                accession_number=accession,
                                retrieved_at=retrieved_at,
                                quality_status=FundamentalQualityStatus.AUTHORITATIVE,
                                validation_status=FundamentalValidationStatus.SEC_CANONICAL,
                                family=FactFamily.REGULATORY,
                                period_kind=kind,
                                form_type=form,
                                fiscal_year=int(item["fy"]) if item.get("fy") not in (None, "") else None,
                                fiscal_period=str(item.get("fp")) if item.get("fp") not in (None, "") else None,
                                taxonomy=str(taxonomy),
                                frame=str(item.get("frame")) if item.get("frame") else None,
                                is_amendment=form.endswith("/A"),
                                raw_payload_hash=sha256_payload(item),
                            )
                        )
        return out

    async def get_estimates(self, security: Security) -> list[EstimateRow]:
        return []

    async def get_company_metrics(self, security: Security) -> list[GuidanceKPI]:
        return []

    async def validate_symbol(self, security: Security) -> bool:
        try:
            await self.get_filings(security)
            return True
        except Exception:
            return False

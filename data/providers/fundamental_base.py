from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from core.contracts.entities import Security
from core.fundamentals.models import EstimateRow, FilingRecord, FundamentalFactRow, GuidanceKPI


class FundamentalProvider(Protocol):
    name: str

    async def get_filings(self, security: Security) -> Sequence[FilingRecord]: ...

    async def get_facts(self, security: Security) -> Sequence[FundamentalFactRow]: ...

    async def get_estimates(self, security: Security) -> Sequence[EstimateRow]: ...

    async def get_company_metrics(self, security: Security) -> Sequence[GuidanceKPI]: ...

    async def validate_symbol(self, security: Security) -> bool: ...


class InvestorRelationsProvider(Protocol):
    name: str

    def ingest_structured(
        self,
        security: Security,
        records: list[dict],
        *,
        retrieved_at: datetime,
    ) -> Sequence[GuidanceKPI]: ...

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, Sequence

from core.contracts.entities import FinancialFact, PriceBar, Security


class SecurityUniverseProvider(Protocol):
    name: str

    async def list_us_securities(self, as_of: date) -> Sequence[Security]: ...


class PriceProvider(Protocol):
    name: str

    async def daily_prices(
        self, security: Security, start: date, end: date
    ) -> Sequence[PriceBar]: ...


class FundamentalsProvider(Protocol):
    name: str

    async def facts_as_of(
        self, security: Security, as_of: datetime
    ) -> Sequence[FinancialFact]: ...


class CorporateActionsProvider(Protocol):
    name: str

    async def actions(self, security: Security, start: date, end: date) -> Sequence[dict]: ...


class MarketProvider(Protocol):
    name: str

    async def snapshot_as_of(self, market: str, as_of: datetime) -> dict: ...

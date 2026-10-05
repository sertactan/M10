from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, Sequence

from core.contracts.entities import FinancialFact, Security
from data.providers.price_base import PriceProvider


class SecurityUniverseProvider(Protocol):
    name: str

    async def list_us_securities(self, as_of: date) -> Sequence[Security]: ...


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


__all__ = ["PriceProvider", "SecurityUniverseProvider", "FundamentalsProvider", "CorporateActionsProvider", "MarketProvider"]

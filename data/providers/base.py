from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, Sequence

from core.contracts.entities import Security
from data.providers.fundamental_base import FundamentalProvider, InvestorRelationsProvider
from data.providers.price_base import PriceProvider


class SecurityUniverseProvider(Protocol):
    name: str

    async def list_us_securities(self, as_of: date) -> Sequence[Security]: ...


class CorporateActionsProvider(Protocol):
    name: str

    async def actions(self, security: Security, start: date, end: date) -> Sequence[dict]: ...


class MarketProvider(Protocol):
    name: str

    async def snapshot_as_of(self, market: str, as_of: datetime) -> dict: ...


__all__ = [
    "PriceProvider",
    "FundamentalProvider",
    "InvestorRelationsProvider",
    "SecurityUniverseProvider",
    "CorporateActionsProvider",
    "MarketProvider",
]

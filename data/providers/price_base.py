from __future__ import annotations

from datetime import date
from typing import Protocol, Sequence

from core.contracts.entities import Security
from core.prices.models import DividendEvent, MarketSnapshot, SourcePriceBar, SplitEvent


class PriceProvider(Protocol):
    name: str

    async def get_history(
        self, security: Security, start: date, end: date
    ) -> Sequence[SourcePriceBar]: ...

    async def get_daily_bar(self, security: Security, trade_date: date) -> SourcePriceBar | None: ...

    async def get_market_snapshot(self, security: Security) -> MarketSnapshot | None: ...

    async def get_splits(
        self, security: Security, start: date | None = None, end: date | None = None
    ) -> Sequence[SplitEvent]: ...

    async def get_dividends(
        self, security: Security, start: date | None = None, end: date | None = None
    ) -> Sequence[DividendEvent]: ...

    async def validate_symbol(self, security: Security) -> bool: ...

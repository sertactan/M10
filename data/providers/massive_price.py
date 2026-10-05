from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from core.contracts.entities import Security
from core.prices.models import (
    AdjustmentStatus,
    DividendEvent,
    MarketSnapshot,
    PriceQualityStatus,
    SourcePriceBar,
    SplitEvent,
)
from data.providers.http_json import JsonHttpClient
from data.providers.price_utils import optional_date, sha256_payload, utc_now


class MassivePriceProvider:
    name = "MASSIVE"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.massive.com",
        timeout_seconds: float = 30.0,
        max_retries: int = 4,
    ) -> None:
        self.api_key = api_key or os.getenv("MASSIVE_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.http = JsonHttpClient(timeout_seconds, max_retries)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _key(self) -> str:
        if not self.api_key:
            raise RuntimeError("MASSIVE_API_KEY is not configured")
        return self.api_key

    async def _aggs(self, ticker: str, start: date, end: date, adjusted: bool) -> dict[str, Any]:
        return await self.http.get_json(
            f"{self.base_url}/v2/aggs/ticker/{ticker}/range/1/day/{start.isoformat()}/{end.isoformat()}",
            params={
                "adjusted": str(adjusted).lower(),
                "sort": "asc",
                "limit": 50000,
                "apiKey": self._key(),
            },
        )

    async def get_history(self, security: Security, start: date, end: date) -> list[SourcePriceBar]:
        raw = await self._aggs(security.ticker, start, end, adjusted=False)
        adj = await self._aggs(security.ticker, start, end, adjusted=True)
        return self.parse_dual_aggregates(
            security.security_id,
            security.ticker,
            raw,
            adj,
            retrieved_at=utc_now(),
        )

    @staticmethod
    def parse_dual_aggregates(
        security_id: str,
        source_symbol: str,
        raw_payload: dict[str, Any],
        adjusted_payload: dict[str, Any],
        *,
        retrieved_at: datetime,
    ) -> list[SourcePriceBar]:
        raw_by_ts = {int(x["t"]): x for x in raw_payload.get("results") or [] if x.get("t") is not None}
        adj_by_ts = {int(x["t"]): x for x in adjusted_payload.get("results") or [] if x.get("t") is not None}
        bars: list[SourcePriceBar] = []
        for ts in sorted(raw_by_ts.keys() & adj_by_ts.keys()):
            r = raw_by_ts[ts]
            a = adj_by_ts[ts]
            d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
            bars.append(
                SourcePriceBar(
                    security_id=security_id,
                    source="MASSIVE",
                    source_symbol=source_symbol,
                    trade_date=d,
                    open=float(r["o"]),
                    high=float(r["h"]),
                    low=float(r["l"]),
                    raw_close=float(r["c"]),
                    adjusted_close=float(a["c"]),
                    volume=float(r.get("v") or 0),
                    vwap=float(r["vw"]) if r.get("vw") is not None else None,
                    retrieved_at=retrieved_at,
                    quality_status=PriceQualityStatus.PRIMARY,
                    adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
                    raw_payload_hash=sha256_payload({"raw": r, "adjusted": a}),
                )
            )
        return bars

    async def get_daily_bar(self, security: Security, trade_date: date) -> SourcePriceBar | None:
        bars = await self.get_history(security, trade_date, trade_date)
        return bars[0] if bars else None

    async def get_market_snapshot(self, security: Security) -> MarketSnapshot | None:
        payload = await self.http.get_json(
            f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers/{security.ticker}",
            params={"apiKey": self._key()},
        )
        ticker = payload.get("ticker") or {}
        day = ticker.get("day") or {}
        price = day.get("c")
        prev = (ticker.get("prevDay") or {}).get("c")
        pct = None
        if price is not None and prev not in (None, 0):
            pct = (float(price) / float(prev) - 1.0) * 100.0
        if price is None:
            return None
        now = utc_now()
        return MarketSnapshot(
            security_id=security.security_id,
            source=self.name,
            source_symbol=security.ticker,
            as_of=now,
            price=float(price),
            day_change_pct=pct,
            volume=float(day.get("v")) if day.get("v") is not None else None,
            retrieved_at=now,
            quality_status=PriceQualityStatus.PRIMARY,
        )

    async def get_splits(
        self, security: Security, start: date | None = None, end: date | None = None
    ) -> list[SplitEvent]:
        params: dict[str, Any] = {"ticker": security.ticker, "limit": 1000, "apiKey": self._key()}
        if start:
            params["execution_date.gte"] = start.isoformat()
        if end:
            params["execution_date.lte"] = end.isoformat()
        payload = await self.http.get_json(f"{self.base_url}/stocks/v1/splits", params=params)
        return self.parse_splits(security.security_id, security.ticker, payload, retrieved_at=utc_now())

    @staticmethod
    def parse_splits(
        security_id: str, source_symbol: str, payload: dict[str, Any], *, retrieved_at: datetime
    ) -> list[SplitEvent]:
        out: list[SplitEvent] = []
        for item in payload.get("results") or []:
            execution = optional_date(item.get("execution_date"))
            split_from = item.get("split_from") or item.get("splitFrom")
            split_to = item.get("split_to") or item.get("splitTo")
            if not execution or split_from in (None, 0) or split_to in (None, 0):
                continue
            out.append(SplitEvent(
                security_id=security_id,
                source="MASSIVE",
                source_symbol=source_symbol,
                execution_date=execution,
                split_from=float(split_from),
                split_to=float(split_to),
                retrieved_at=retrieved_at,
                quality_status=PriceQualityStatus.PRIMARY,
            ))
        return out

    async def get_dividends(
        self, security: Security, start: date | None = None, end: date | None = None
    ) -> list[DividendEvent]:
        params: dict[str, Any] = {"ticker": security.ticker, "limit": 1000, "apiKey": self._key()}
        if start:
            params["ex_dividend_date.gte"] = start.isoformat()
        if end:
            params["ex_dividend_date.lte"] = end.isoformat()
        payload = await self.http.get_json(f"{self.base_url}/stocks/v1/dividends", params=params)
        return self.parse_dividends(security.security_id, security.ticker, payload, retrieved_at=utc_now())

    @staticmethod
    def parse_dividends(
        security_id: str, source_symbol: str, payload: dict[str, Any], *, retrieved_at: datetime
    ) -> list[DividendEvent]:
        out: list[DividendEvent] = []
        for item in payload.get("results") or []:
            ex_date = optional_date(item.get("ex_dividend_date"))
            amount = item.get("cash_amount")
            if not ex_date or amount is None:
                continue
            out.append(DividendEvent(
                security_id=security_id,
                source="MASSIVE",
                source_symbol=source_symbol,
                ex_date=ex_date,
                cash_amount=float(amount),
                currency=item.get("currency") or item.get("currency_code"),
                declaration_date=optional_date(item.get("declaration_date")),
                record_date=optional_date(item.get("record_date")),
                pay_date=optional_date(item.get("pay_date")),
                retrieved_at=retrieved_at,
                quality_status=PriceQualityStatus.PRIMARY,
            ))
        return out

    async def validate_symbol(self, security: Security) -> bool:
        try:
            payload = await self.http.get_json(
                f"{self.base_url}/v3/reference/tickers/{security.ticker}",
                params={"apiKey": self._key()},
            )
            return bool((payload.get("results") or {}).get("ticker"))
        except Exception:
            return False

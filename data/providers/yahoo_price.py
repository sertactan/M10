from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

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
from data.providers.price_utils import sha256_payload, utc_now


class YahooCompatiblePriceProvider:
    name = "YAHOO_COMPAT"

    def __init__(
        self,
        *,
        base_url: str = "https://query1.finance.yahoo.com/v8/finance/chart",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        primary = base_url.rstrip("/")
        self.base_urls = [primary]
        if primary == "https://query1.finance.yahoo.com/v8/finance/chart":
            self.base_urls = [
                "https://query2.finance.yahoo.com/v8/finance/chart",
                "https://query1.finance.yahoo.com/v8/finance/chart",
            ]
        self.base_url = self.base_urls[0]
        self.http = JsonHttpClient(timeout_seconds, max_retries)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    @staticmethod
    def _epoch(d: date, *, exclusive_end: bool = False) -> int:
        dt = datetime.combine(d, time.min, tzinfo=timezone.utc)
        if exclusive_end:
            from datetime import timedelta
            dt += timedelta(days=1)
        return int(dt.timestamp())

    async def _get_chart_json(
        self,
        ticker: str,
        *,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        errors: list[str] = []
        for base_url in self.base_urls:
            try:
                return await self.http.get_json(
                    f"{base_url}/{ticker}",
                    params=params,
                    headers=self.headers,
                )
            except Exception as exc:
                errors.append(f"{base_url}: {exc}")
        raise RuntimeError(
            f"Yahoo chart hosts unavailable for {ticker}: " + "; ".join(errors)
        )

    async def _chart(self, ticker: str, start: date, end: date) -> dict[str, Any]:
        return await self._get_chart_json(
            ticker,
            params={
                "period1": self._epoch(start),
                "period2": self._epoch(end, exclusive_end=True),
                "interval": "1d",
                "events": "div,splits",
                "includeAdjustedClose": "true",
            },
        )

    async def get_history(self, security: Security, start: date, end: date) -> list[SourcePriceBar]:
        payload = await self._chart(security.ticker, start, end)
        return self.parse_chart(security.security_id, security.ticker, payload, retrieved_at=utc_now())

    @staticmethod
    def parse_chart(
        security_id: str, source_symbol: str, payload: dict[str, Any], *, retrieved_at: datetime
    ) -> list[SourcePriceBar]:
        chart = payload.get("chart") or {}
        result = (chart.get("result") or [None])[0]
        if not result:
            return []
        timestamps = result.get("timestamp") or []
        indicators = result.get("indicators") or {}
        quote = (indicators.get("quote") or [{}])[0]
        adj = (indicators.get("adjclose") or [{}])[0].get("adjclose") or []
        out: list[SourcePriceBar] = []
        for i, ts in enumerate(timestamps):
            try:
                o = quote.get("open", [])[i]
                h = quote.get("high", [])[i]
                l = quote.get("low", [])[i]
                c = quote.get("close", [])[i]
                v = quote.get("volume", [])[i]
            except IndexError:
                continue
            if None in (o, h, l, c):
                continue
            adjusted = adj[i] if i < len(adj) and adj[i] is not None else c
            row = {"t": ts, "o": o, "h": h, "l": l, "c": c, "v": v, "adj": adjusted}
            out.append(SourcePriceBar(
                security_id=security_id, source="YAHOO_COMPAT", source_symbol=source_symbol,
                trade_date=datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
                open=float(o), high=float(h), low=float(l), raw_close=float(c),
                adjusted_close=float(adjusted), volume=float(v or 0), retrieved_at=retrieved_at,
                quality_status=PriceQualityStatus.FALLBACK_ONLY,
                adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
                raw_payload_hash=sha256_payload(row),
            ))
        return out

    async def get_daily_bar(self, security: Security, trade_date: date) -> SourcePriceBar | None:
        rows = await self.get_history(security, trade_date, trade_date)
        return rows[0] if rows else None

    async def get_market_snapshot(self, security: Security) -> MarketSnapshot | None:
        payload = await self._get_chart_json(
            security.ticker,
            params={"range": "5d", "interval": "1d", "includeAdjustedClose": "true"},
        )
        rows = self.parse_chart(security.security_id, security.ticker, payload, retrieved_at=utc_now())
        if not rows:
            return None
        bar = rows[-1]
        pct = None
        if len(rows) >= 2 and rows[-2].adjusted_close:
            pct = (bar.adjusted_close / rows[-2].adjusted_close - 1.0) * 100.0
        return MarketSnapshot(
            security_id=security.security_id, source=self.name, source_symbol=security.ticker,
            as_of=bar.retrieved_at, price=bar.adjusted_close, day_change_pct=pct, volume=bar.volume,
            retrieved_at=bar.retrieved_at, quality_status=PriceQualityStatus.FALLBACK_ONLY,
        )

    async def get_splits(self, security: Security, start: date | None = None, end: date | None = None) -> list[SplitEvent]:
        start = start or date(1970, 1, 1)
        end = end or date.today()
        payload = await self._chart(security.ticker, start, end)
        result = (((payload.get("chart") or {}).get("result") or [None])[0] or {})
        events = ((result.get("events") or {}).get("splits") or {})
        now = utc_now()
        out: list[SplitEvent] = []
        for item in events.values():
            numerator = item.get("numerator")
            denominator = item.get("denominator")
            ts = item.get("date")
            if not ts or not numerator or not denominator:
                continue
            out.append(SplitEvent(
                security_id=security.security_id, source=self.name, source_symbol=security.ticker,
                execution_date=datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
                split_from=float(denominator), split_to=float(numerator), retrieved_at=now,
                quality_status=PriceQualityStatus.FALLBACK_ONLY,
            ))
        return out

    async def get_dividends(self, security: Security, start: date | None = None, end: date | None = None) -> list[DividendEvent]:
        start = start or date(1970, 1, 1)
        end = end or date.today()
        payload = await self._chart(security.ticker, start, end)
        result = (((payload.get("chart") or {}).get("result") or [None])[0] or {})
        events = ((result.get("events") or {}).get("dividends") or {})
        now = utc_now()
        out: list[DividendEvent] = []
        for item in events.values():
            ts = item.get("date")
            amount = item.get("amount")
            if not ts or amount is None:
                continue
            out.append(DividendEvent(
                security_id=security.security_id, source=self.name, source_symbol=security.ticker,
                ex_date=datetime.fromtimestamp(int(ts), tz=timezone.utc).date(), cash_amount=float(amount),
                currency=None, retrieved_at=now, quality_status=PriceQualityStatus.FALLBACK_ONLY,
            ))
        return out

    async def validate_symbol(self, security: Security) -> bool:
        try:
            payload = await self._get_chart_json(
                security.ticker,
                params={"range": "5d", "interval": "1d"},
            )
            result = (payload.get("chart") or {}).get("result") or []
            return bool(result)
        except Exception:
            return False

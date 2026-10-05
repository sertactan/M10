from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from core.universe.identity import exchange_from_mic, normalize_cik
from core.universe.models import TickerChangeEvent, UniverseRecord
from data.providers.http_json import JsonHttpClient


class MassiveUniverseProvider:
    name = "MASSIVE"
    TARGET_MICS = {"XNAS", "XNYS", "XASE"}

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

    def _require_key(self) -> str:
        if not self.api_key:
            raise RuntimeError("MASSIVE_API_KEY is not configured")
        return self.api_key

    @staticmethod
    def _with_api_key(url: str, api_key: str) -> str:
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["apiKey"] = api_key
        return urlunparse(parsed._replace(query=urlencode(query)))

    async def list_us_securities(
        self, *, as_of: date | None = None, active: bool = True
    ) -> list[UniverseRecord]:
        api_key = self._require_key()
        url = f"{self.base_url}/v3/reference/tickers"
        params: dict[str, Any] | None = {
            "market": "stocks",
            "locale": "us",
            "active": str(active).lower(),
            "limit": 1000,
            "sort": "ticker",
            "order": "asc",
            "apiKey": api_key,
        }
        if as_of is not None:
            params["date"] = as_of.isoformat()

        out: list[UniverseRecord] = []
        while url:
            payload = await self.http.get_json(url, params=params)
            out.extend(self.parse_tickers_payload(payload))
            next_url = payload.get("next_url")
            if not next_url:
                break
            url = self._with_api_key(str(next_url), api_key)
            params = None
        return out

    @classmethod
    def parse_tickers_payload(
        cls, payload: dict[str, Any], *, availability_date: datetime | None = None
    ) -> list[UniverseRecord]:
        availability = availability_date or datetime.now(timezone.utc)
        out: list[UniverseRecord] = []
        for item in payload.get("results") or []:
            mic = str(item.get("primary_exchange") or "").upper()
            if mic not in cls.TARGET_MICS:
                continue
            exchange = exchange_from_mic(mic)
            if exchange is None:
                continue
            ticker = str(item.get("ticker") or "").strip().upper()
            name = str(item.get("name") or "").strip()
            if not ticker or not name:
                continue
            delisted_raw = item.get("delisted_utc")
            delisted_date = None
            if delisted_raw:
                delisted_date = datetime.fromisoformat(
                    str(delisted_raw).replace("Z", "+00:00")
                ).date()
            updated_raw = item.get("last_updated_utc")
            updated = None
            if updated_raw:
                updated = datetime.fromisoformat(str(updated_raw).replace("Z", "+00:00"))
            out.append(
                UniverseRecord(
                    ticker=ticker,
                    name=name,
                    exchange=exchange,
                    exchange_mic=mic,
                    active=bool(item.get("active", True)),
                    provider="MASSIVE",
                    availability_date=availability,
                    security_type=item.get("type"),
                    cik=normalize_cik(item.get("cik")),
                    composite_figi=item.get("composite_figi"),
                    share_class_figi=item.get("share_class_figi"),
                    currency=(item.get("currency_symbol") or "USD").upper(),
                    locale=item.get("locale") or "us",
                    delisted_date=delisted_date,
                    provider_last_updated=updated,
                )
            )
        return out

    async def ticker_events(self, identifier: str) -> list[TickerChangeEvent]:
        api_key = self._require_key()
        payload = await self.http.get_json(
            f"{self.base_url}/vX/reference/tickers/{identifier}/events",
            params={"types": "ticker_change", "apiKey": api_key},
        )
        return self.parse_ticker_events(payload)

    @staticmethod
    def parse_ticker_events(
        payload: dict[str, Any], *, availability_date: datetime | None = None
    ) -> list[TickerChangeEvent]:
        availability = availability_date or datetime.now(timezone.utc)
        out: list[TickerChangeEvent] = []
        results = payload.get("results") or {}
        for event in results.get("events") or []:
            if event.get("type") != "ticker_change":
                continue
            ticker = str(
                (event.get("ticker_change") or {}).get("ticker") or ""
            ).strip().upper()
            event_date = event.get("date")
            if not ticker or not event_date:
                continue
            out.append(
                TickerChangeEvent(
                    event_date=date.fromisoformat(str(event_date)),
                    ticker=ticker,
                    provider="MASSIVE",
                    availability_date=availability,
                )
            )
        return sorted(out, key=lambda e: e.event_date)

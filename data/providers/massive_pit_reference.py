from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from data.providers.http_json import JsonHttpClient


@dataclass(frozen=True)
class MassivePITReference:
    ticker: str
    as_of_date: date
    market_cap: float | None
    weighted_shares_outstanding: float | None
    share_class_shares_outstanding: float | None
    sic_code: str | None
    sic_description: str | None
    primary_exchange: str | None
    security_type: str | None
    active: bool | None
    source: str = "MASSIVE_PIT"


class MassivePITReferenceProvider:
    """Point-in-time ticker details used only as dated reference evidence."""

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

    async def get(self, ticker: str, as_of_date: date) -> MassivePITReference:
        payload = await self.http.get_json(
            f"{self.base_url}/v3/reference/tickers/{ticker}",
            params={"date": as_of_date.isoformat(), "apiKey": self._require_key()},
        )
        return self.parse(payload, ticker=ticker, as_of_date=as_of_date)

    @staticmethod
    def parse(
        payload: dict[str, Any],
        *,
        ticker: str,
        as_of_date: date,
    ) -> MassivePITReference:
        item = payload.get("results") or {}

        def number(*keys: str) -> float | None:
            for key in keys:
                value = item.get(key)
                if value not in (None, ""):
                    return float(value)
            return None

        return MassivePITReference(
            ticker=str(item.get("ticker") or ticker).upper(),
            as_of_date=as_of_date,
            market_cap=number("market_cap"),
            weighted_shares_outstanding=number(
                "weighted_shares_outstanding",
                "outstanding_shares",
            ),
            share_class_shares_outstanding=number(
                "share_class_shares_outstanding",
                "share_class_shares_outstanding_value",
            ),
            sic_code=(str(item["sic_code"]) if item.get("sic_code") is not None else None),
            sic_description=(
                str(item["sic_description"])
                if item.get("sic_description") is not None
                else None
            ),
            primary_exchange=(
                str(item["primary_exchange"])
                if item.get("primary_exchange") is not None
                else None
            ),
            security_type=(
                str(item["type"]) if item.get("type") is not None else None
            ),
            active=(bool(item["active"]) if item.get("active") is not None else None),
        )

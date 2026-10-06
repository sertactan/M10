from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.universe.identity import EXCHANGE_TO_MIC, exchange_from_sec_name, normalize_cik
from core.universe.models import UniverseRecord
from data.cache.sec_json_mirror import SecJsonMirror
from data.providers.http_json import JsonHttpClient
from data.providers.sec_access import resolve_sec_user_agent


class SECEdgarUniverseProvider:
    name = "SEC_EDGAR"

    def __init__(
        self,
        *,
        base_url: str = "https://www.sec.gov",
        user_agent: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        mirror_root: str | Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = resolve_sec_user_agent(user_agent)
        self.http = JsonHttpClient(timeout_seconds, max_retries)
        self.mirror = SecJsonMirror(mirror_root) if mirror_root is not None else None

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    async def list_current_us_securities(self) -> list[UniverseRecord]:
        url = f"{self.base_url}/files/company_tickers_exchange.json"
        if self.mirror is not None:
            result = await self.mirror.fetch_json(self.http, url, headers=self._headers())
            payload = result.payload
        else:
            payload = await self.http.get_json(url, headers=self._headers())
        return self.parse_ticker_exchange_payload(payload)

    @staticmethod
    def parse_ticker_exchange_payload(
        payload: dict[str, Any], *, availability_date: datetime | None = None
    ) -> list[UniverseRecord]:
        availability = availability_date or datetime.now(timezone.utc)
        fields = payload.get("fields") or []
        rows = payload.get("data") or []
        indexes = {str(name): idx for idx, name in enumerate(fields)}
        required = {"cik", "name", "ticker", "exchange"}
        if not required.issubset(indexes):
            raise ValueError(f"Unexpected SEC ticker payload fields: {fields}")

        out: list[UniverseRecord] = []
        for row in rows:
            exchange = exchange_from_sec_name(row[indexes["exchange"]])
            if exchange is None:
                continue
            ticker = str(row[indexes["ticker"]] or "").strip().upper()
            name = str(row[indexes["name"]] or "").strip()
            if not ticker or not name:
                continue
            out.append(
                UniverseRecord(
                    ticker=ticker,
                    name=name,
                    exchange=exchange,
                    exchange_mic=EXCHANGE_TO_MIC[exchange],
                    active=True,
                    provider="SEC_EDGAR",
                    availability_date=availability,
                    security_type=None,
                    cik=normalize_cik(row[indexes["cik"]]),
                    currency="USD",
                    locale="us",
                )
            )
        return out

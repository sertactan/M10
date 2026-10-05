from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from data.providers.http_json import JsonHttpClient


@dataclass(frozen=True)
class FinnhubSymbol:
    symbol: str
    display_symbol: str
    description: str
    security_type: str | None


class FinnhubUniverseProvider:
    name = "FINNHUB"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://finnhub.io/api/v1",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.http = JsonHttpClient(timeout_seconds, max_retries)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def list_us_symbols(self) -> list[FinnhubSymbol]:
        if not self.api_key:
            raise RuntimeError("FINNHUB_API_KEY is not configured")
        payload = await self.http.get_json(
            f"{self.base_url}/stock/symbol",
            params={"exchange": "US", "token": self.api_key},
        )
        return self.parse_symbol_payload(payload)

    @staticmethod
    def parse_symbol_payload(payload: list[dict[str, Any]]) -> list[FinnhubSymbol]:
        out: list[FinnhubSymbol] = []
        for item in payload:
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            out.append(
                FinnhubSymbol(
                    symbol=symbol,
                    display_symbol=str(item.get("displaySymbol") or symbol).strip().upper(),
                    description=str(item.get("description") or "").strip(),
                    security_type=item.get("type"),
                )
            )
        return out

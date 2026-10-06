from __future__ import annotations

import asyncio
import csv
import io

import httpx

from core.universe.global_models import GlobalReferenceListing


DEFAULT_ADANOS_CORE_URL = (
    "https://raw.githubusercontent.com/adanos-software/"
    "free-ticker-database/main/data/core_listings.csv"
)


class AdanosGlobalReferenceProvider:
    """Broad global ticker reference source.

    This provider is deliberately REFERENCE_ONLY. The upstream project documents
    mixed source-licensing status, so rows fetched here are never promoted to
    authoritative market-data or backtest evidence by this adapter.
    """

    name = "ADANOS_REFERENCE"

    def __init__(
        self,
        *,
        url: str = DEFAULT_ADANOS_CORE_URL,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def _get_text(self) -> str:
        last_error: Exception | None = None
        headers = {
            "User-Agent": "S15.3-Research-Terminal/2B global-reference-sync",
            "Accept": "text/csv,text/plain,*/*",
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.get(self.url, headers=headers)
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt >= self.max_retries:
                            response.raise_for_status()
                        retry_after = response.headers.get("Retry-After")
                        delay = (
                            float(retry_after)
                            if retry_after
                            else min(8.0, 0.5 * (2**attempt))
                        )
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        break
                    await asyncio.sleep(min(8.0, 0.5 * (2**attempt)))
        raise RuntimeError(f"Global reference download failed: {last_error}")

    async def list_reference_securities(self) -> list[GlobalReferenceListing]:
        return self.parse_core_listings(await self._get_text())

    @staticmethod
    def parse_core_listings(text: str) -> list[GlobalReferenceListing]:
        rows = csv.DictReader(io.StringIO(text))
        required = {"listing_key", "ticker", "exchange", "name"}
        if rows.fieldnames is None or not required.issubset(set(rows.fieldnames)):
            raise ValueError(
                f"Unexpected global reference columns: {rows.fieldnames}"
            )

        out: list[GlobalReferenceListing] = []
        for row in rows:
            listing_key = (row.get("listing_key") or "").strip()
            ticker = (row.get("ticker") or "").strip().upper()
            exchange = (row.get("exchange") or "").strip().upper()
            name = (row.get("name") or "").strip()
            if not listing_key or not ticker or not exchange or not name:
                continue
            out.append(
                GlobalReferenceListing(
                    listing_key=listing_key,
                    ticker=ticker,
                    exchange=exchange,
                    name=name,
                    asset_type=(row.get("asset_type") or "").strip() or None,
                    country=(row.get("country") or "").strip() or None,
                    country_code=(row.get("country_code") or "").strip().upper() or None,
                    isin=(row.get("isin") or "").strip().upper() or None,
                    aliases=(row.get("aliases") or "").strip() or None,
                )
            )
        return out

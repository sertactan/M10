from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any

import httpx

from core.universe.identity import EXCHANGE_TO_MIC, exchange_from_sec_name, normalize_cik
from core.universe.models import UniverseRecord


class StockDataPitUnavailable(RuntimeError):
    pass


class StockDataPitUniverseProvider:
    """Public-domain PIT SEC ticker/exchange intervals from TylerJForstrom/Stock-Data.

    The producer publishes a manifest with an explicit reconstructable floor and
    SHA256 for every interval artifact. Dates before that floor are refused.
    """

    name = "STOCK_DATA_PIT"
    manifest_url = (
        "https://raw.githubusercontent.com/TylerJForstrom/Stock-Data/"
        "main/data/symbols/pit/manifest.json"
    )
    data_url = (
        "https://raw.githubusercontent.com/TylerJForstrom/Stock-Data/"
        "main/data/symbols/pit/sec_company_tickers_exchange.jsonl"
    )
    data_name = "sec_company_tickers_exchange.jsonl"

    def __init__(self, *, timeout_seconds: float = 60.0) -> None:
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _active(row: dict[str, Any], as_of: date) -> bool:
        valid_from = date.fromisoformat(str(row["valid_from"]))
        valid_to_raw = row.get("valid_to")
        valid_to = date.fromisoformat(str(valid_to_raw)) if valid_to_raw else None
        return valid_from <= as_of and (valid_to is None or as_of < valid_to)

    @classmethod
    def parse(
        cls,
        *,
        manifest: dict[str, Any],
        jsonl_bytes: bytes,
        as_of: date,
        availability_date: datetime | None = None,
    ) -> list[UniverseRecord]:
        floor_raw = manifest.get("reconstructable_from")
        if not isinstance(floor_raw, str):
            raise StockDataPitUnavailable("PIT manifest has no reconstructable_from")
        floor = date.fromisoformat(floor_raw)
        if as_of < floor:
            raise StockDataPitUnavailable(
                f"Public PIT archive begins {floor.isoformat()}; requested "
                f"{as_of.isoformat()} is earlier"
            )

        files = manifest.get("files")
        if not isinstance(files, list):
            raise StockDataPitUnavailable("PIT manifest files list is missing")
        entry = next(
            (item for item in files if item.get("name") == cls.data_name),
            None,
        )
        if entry is None:
            raise StockDataPitUnavailable(
                f"PIT manifest does not list {cls.data_name}"
            )
        digest = hashlib.sha256(jsonl_bytes).hexdigest()
        if digest != entry.get("sha256"):
            raise StockDataPitUnavailable(
                f"PIT artifact SHA256 mismatch for {cls.data_name}"
            )

        availability = availability_date or datetime.now(timezone.utc)
        out: list[UniverseRecord] = []
        for raw_line in jsonl_bytes.decode("utf-8").splitlines():
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            if not cls._active(row, as_of):
                continue
            exchange = exchange_from_sec_name(row.get("exchange"))
            if exchange is None:
                continue
            ticker = str(row.get("ticker") or "").strip().upper()
            name = str(row.get("title") or "").strip()
            cik = normalize_cik(row.get("cik"))
            if not ticker or not name:
                continue
            out.append(
                UniverseRecord(
                    ticker=ticker,
                    name=name,
                    exchange=exchange,
                    exchange_mic=EXCHANGE_TO_MIC[exchange],
                    active=False,  # historical membership never asserts current activity
                    provider=cls.name,
                    availability_date=availability,
                    security_type=None,
                    cik=cik,
                    currency="USD",
                    locale="us",
                )
            )
        return out

    async def list_historical_us_securities(self, as_of: date) -> list[UniverseRecord]:
        headers = {
            "User-Agent": "S15.3 Research Terminal (https://github.com/sertactan/M10)",
            "Accept": "application/json,text/plain,*/*",
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            manifest_response, data_response = await asyncio.gather(
                client.get(self.manifest_url),
                client.get(self.data_url),
            )
            manifest_response.raise_for_status()
            data_response.raise_for_status()
            manifest = manifest_response.json()
            return self.parse(
                manifest=manifest,
                jsonl_bytes=data_response.content,
                as_of=as_of,
                availability_date=datetime.now(timezone.utc),
            )

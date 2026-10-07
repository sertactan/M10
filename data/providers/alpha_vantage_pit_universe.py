from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime, timezone

import httpx

from core.contracts.enums import Exchange
from core.universe.identity import EXCHANGE_TO_MIC
from core.universe.models import UniverseRecord


class AlphaVantagePitUnavailable(RuntimeError):
    pass


class AlphaVantagePitUniverseProvider:
    """Historical US listing-status snapshots from Alpha Vantage.

    The public LISTING_STATUS endpoint accepts a historical date after
    2010-01-01. This adapter uses only the active listing set for the requested
    date and filters out ETFs/funds where assetType is available.
    """

    name = "ALPHAVANTAGE_PIT"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://www.alphavantage.co/query",
        timeout_seconds: float = 90.0,
    ) -> None:
        self.api_key = api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _exchange(value: str | None) -> Exchange | None:
        text = (value or "").strip().upper()
        mapping = {
            "NASDAQ": Exchange.NASDAQ,
            "NASDAQ GLOBAL SELECT MARKET": Exchange.NASDAQ,
            "NASDAQ GLOBAL MARKET": Exchange.NASDAQ,
            "NASDAQ CAPITAL MARKET": Exchange.NASDAQ,
            "NYSE": Exchange.NYSE,
            "NEW YORK STOCK EXCHANGE": Exchange.NYSE,
            "NYSE MKT": Exchange.AMEX,
            "NYSE AMERICAN": Exchange.AMEX,
            "AMEX": Exchange.AMEX,
        }
        return mapping.get(text)

    @classmethod
    def parse_csv(
        cls,
        payload: str,
        *,
        as_of: date,
        availability_date: datetime | None = None,
    ) -> list[UniverseRecord]:
        if as_of <= date(2010, 1, 1):
            raise AlphaVantagePitUnavailable(
                "Alpha Vantage LISTING_STATUS supports dates later than 2010-01-01"
            )
        stripped = payload.lstrip()
        if not stripped:
            raise AlphaVantagePitUnavailable("Alpha Vantage LISTING_STATUS returned empty data")
        if stripped.startswith("{"):
            raise AlphaVantagePitUnavailable(
                "Alpha Vantage LISTING_STATUS returned an API error/rate-limit payload"
            )

        reader = csv.DictReader(io.StringIO(payload))
        required = {"symbol", "name", "exchange"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise AlphaVantagePitUnavailable(
                "Alpha Vantage LISTING_STATUS CSV is missing required columns"
            )

        availability = availability_date or datetime.now(timezone.utc)
        out: list[UniverseRecord] = []
        for row in reader:
            asset_type = (row.get("assetType") or "").strip().lower()
            if asset_type and asset_type not in {"stock", "common stock"}:
                continue
            status = (row.get("status") or "Active").strip().lower()
            if status and status != "active":
                continue
            exchange = cls._exchange(row.get("exchange"))
            if exchange is None:
                continue
            ticker = (row.get("symbol") or "").strip().upper()
            name = (row.get("name") or "").strip()
            if not ticker or not name:
                continue
            ipo_date = None
            ipo_raw = (row.get("ipoDate") or "").strip()
            if ipo_raw and ipo_raw.lower() not in {"null", "none", "n/a"}:
                try:
                    ipo_date = date.fromisoformat(ipo_raw)
                except ValueError:
                    ipo_date = None

            out.append(
                UniverseRecord(
                    ticker=ticker,
                    name=name,
                    exchange=exchange,
                    exchange_mic=EXCHANGE_TO_MIC[exchange],
                    active=False,
                    provider=cls.name,
                    availability_date=availability,
                    security_type="CS",
                    currency="USD",
                    locale="us",
                    ipo_date=ipo_date,
                )
            )
        if not out:
            raise AlphaVantagePitUnavailable(
                "Alpha Vantage LISTING_STATUS produced no supported US common-stock rows"
            )
        return out

    async def list_historical_us_securities(self, as_of: date) -> list[UniverseRecord]:
        if not self.api_key:
            raise AlphaVantagePitUnavailable("ALPHAVANTAGE_API_KEY is not configured")
        if as_of <= date(2010, 1, 1):
            raise AlphaVantagePitUnavailable(
                "Alpha Vantage LISTING_STATUS supports dates later than 2010-01-01"
            )
        params = {
            "function": "LISTING_STATUS",
            "date": as_of.isoformat(),
            "state": "active",
            "apikey": self.api_key,
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "S15.3 Research Terminal"},
        ) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
        return self.parse_csv(
            response.text,
            as_of=as_of,
            availability_date=datetime.now(timezone.utc),
        )

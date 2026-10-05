from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from core.contracts.entities import Security
from core.prices.models import (
    AdjustmentStatus,
    DividendEvent,
    MarketSnapshot,
    PriceQualityStatus,
    SourcePriceBar,
    SplitEvent,
)
from data.providers.price_utils import parse_date, sha256_payload, utc_now


class StooqPriceProvider:
    name = "STOOQ"

    def __init__(self, *, base_url: str = "https://stooq.com/q/d/l/", timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def source_symbol(ticker: str) -> str:
        return ticker.lower().replace("-", ".") + ".us"

    async def get_history(self, security: Security, start: date, end: date) -> list[SourcePriceBar]:
        symbol = self.source_symbol(security.ticker)
        params = {
            "s": symbol,
            "d1": start.strftime("%Y%m%d"),
            "d2": end.strftime("%Y%m%d"),
            "i": "d",
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            return self.parse_individual_csv(
                security.security_id, symbol, response.text, retrieved_at=utc_now()
            )

    @staticmethod
    def parse_individual_csv(
        security_id: str, source_symbol: str, text: str, *, retrieved_at: datetime
    ) -> list[SourcePriceBar]:
        reader = csv.DictReader(io.StringIO(text))
        out: list[SourcePriceBar] = []
        for row in reader:
            if not row.get("Date") or not row.get("Close"):
                continue
            close = float(row["Close"])
            out.append(SourcePriceBar(
                security_id=security_id,
                source="STOOQ",
                source_symbol=source_symbol,
                trade_date=parse_date(row["Date"]),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                raw_close=close,
                adjusted_close=close,
                volume=float(row.get("Volume") or 0),
                retrieved_at=retrieved_at,
                quality_status=PriceQualityStatus.BOOTSTRAP,
                adjustment_status=AdjustmentStatus.RAW_ONLY,
                raw_payload_hash=sha256_payload(row),
            ))
        return out

    def ingest_bulk_zip(
        self,
        zip_path: str | Path,
        *,
        security_lookup,
        retrieved_at: datetime | None = None,
    ) -> list[SourcePriceBar]:
        now = retrieved_at or utc_now()
        out: list[SourcePriceBar] = []
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                if member.endswith("/") or not member.lower().endswith((".txt", ".csv")):
                    continue
                text = zf.read(member).decode("utf-8", errors="replace")
                out.extend(self._parse_bulk_text(text, member, security_lookup, now))
        return out


    def iter_bulk_zip_series(
        self,
        zip_path: str | Path,
        *,
        security_lookup,
        retrieved_at: datetime | None = None,
    ):
        """Yield provider-isolated series one group at a time to limit memory use."""
        now = retrieved_at or utc_now()
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                if member.endswith("/") or not member.lower().endswith((".txt", ".csv")):
                    continue
                text = zf.read(member).decode("utf-8", errors="replace")
                rows = self._parse_bulk_text(text, member, security_lookup, now)
                groups: dict[tuple[str, str], list[SourcePriceBar]] = {}
                for bar in rows:
                    groups.setdefault((bar.security_id, bar.source_symbol), []).append(bar)
                for group in groups.values():
                    yield group

    @staticmethod
    def _parse_bulk_text(text: str, member: str, security_lookup, retrieved_at: datetime) -> list[SourcePriceBar]:
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return []
        first = lines[0].upper()
        out: list[SourcePriceBar] = []
        if "<TICKER>" in first or "<DATE>" in first:
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                symbol = str(row.get("<TICKER>") or "").strip().lower()
                ticker = symbol.split(".")[0].upper().replace("_", "-")
                security_id = security_lookup(ticker)
                if not security_id:
                    continue
                close = float(row["<CLOSE>"])
                out.append(SourcePriceBar(
                    security_id=security_id,
                    source="STOOQ",
                    source_symbol=symbol,
                    trade_date=parse_date(row["<DATE>"]),
                    open=float(row["<OPEN>"]), high=float(row["<HIGH>"]), low=float(row["<LOW>"]),
                    raw_close=close, adjusted_close=close, volume=float(row.get("<VOL>") or 0),
                    retrieved_at=retrieved_at, quality_status=PriceQualityStatus.BOOTSTRAP,
                    adjustment_status=AdjustmentStatus.RAW_ONLY, raw_payload_hash=sha256_payload(row),
                ))
            return out

        # Some Stooq bulk archives use one symbol per file with normal Date/Open/... headers.
        filename_symbol = Path(member).stem.lower()
        ticker = filename_symbol.split(".")[0].upper().replace("_", "-")
        security_id = security_lookup(ticker)
        if not security_id:
            return []
        return StooqPriceProvider.parse_individual_csv(
            security_id, filename_symbol, text, retrieved_at=retrieved_at
        )

    async def get_daily_bar(self, security: Security, trade_date: date) -> SourcePriceBar | None:
        bars = await self.get_history(security, trade_date, trade_date)
        return bars[0] if bars else None

    async def get_market_snapshot(self, security: Security) -> MarketSnapshot | None:
        bars = await self.get_history(security, date.today() - timedelta(days=15), date.today())
        if not bars:
            return None
        bar = bars[-1]
        return MarketSnapshot(
            security_id=security.security_id, source=self.name, source_symbol=bar.source_symbol,
            as_of=bar.retrieved_at, price=bar.raw_close, day_change_pct=None, volume=bar.volume,
            retrieved_at=bar.retrieved_at, quality_status=PriceQualityStatus.BOOTSTRAP,
        )

    async def get_splits(self, security: Security, start: date | None = None, end: date | None = None) -> list[SplitEvent]:
        return []

    async def get_dividends(self, security: Security, start: date | None = None, end: date | None = None) -> list[DividendEvent]:
        return []

    async def validate_symbol(self, security: Security) -> bool:
        try:
            return bool(await self.get_daily_bar(security, date.today()))
        except Exception:
            return False

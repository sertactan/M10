from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd

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


class SimFinPriceProvider:
    name = "SIMFIN"

    def __init__(self, bulk_path: str | Path | None = None) -> None:
        self.bulk_path = Path(bulk_path) if bulk_path else None
        self._frame: pd.DataFrame | None = None

    @property
    def configured(self) -> bool:
        return self.bulk_path is not None and self.bulk_path.exists()

    def _load(self) -> pd.DataFrame:
        if self._frame is not None:
            return self._frame
        if not self.configured:
            raise RuntimeError("SIMFIN_PRICE_BULK_PATH is not configured or missing")
        path = self.bulk_path
        assert path is not None
        if path.suffix.lower() == ".zip":
            self._frame = pd.read_csv(path, compression="zip")
        else:
            self._frame = pd.read_csv(path)
        return self._frame

    @staticmethod
    def _col(frame: pd.DataFrame, *names: str) -> str | None:
        lowered = {str(c).strip().lower(): str(c) for c in frame.columns}
        for name in names:
            hit = lowered.get(name.strip().lower())
            if hit:
                return hit
        return None

    async def get_history(self, security: Security, start: date, end: date) -> list[SourcePriceBar]:
        if not self.configured:
            raise RuntimeError("SIMFIN_PRICE_BULK_PATH is not configured or missing")
        assert self.bulk_path is not None
        matches: list[pd.DataFrame] = []
        compression = "zip" if self.bulk_path.suffix.lower() == ".zip" else "infer"
        for chunk in pd.read_csv(self.bulk_path, compression=compression, chunksize=250_000):
            ticker_col = self._col(chunk, "Ticker", "Symbol")
            date_col = self._col(chunk, "Date")
            if not ticker_col or not date_col:
                raise ValueError("SimFin share-price dataset requires Ticker/Symbol and Date columns")
            subset = chunk[chunk[ticker_col].astype(str).str.upper() == security.ticker.upper()].copy()
            if subset.empty:
                continue
            subset[date_col] = pd.to_datetime(subset[date_col]).dt.date
            subset = subset[(subset[date_col] >= start) & (subset[date_col] <= end)]
            if not subset.empty:
                matches.append(subset)
        if not matches:
            return []
        return self.parse_frame(
            security.security_id, security.ticker, pd.concat(matches, ignore_index=True),
            retrieved_at=utc_now(),
        )

    @classmethod
    def parse_frame(
        cls, security_id: str, source_symbol: str, frame: pd.DataFrame, *, retrieved_at: datetime
    ) -> list[SourcePriceBar]:
        if frame.empty:
            return []
        date_col = cls._col(frame, "Date")
        open_col = cls._col(frame, "Open")
        high_col = cls._col(frame, "High")
        low_col = cls._col(frame, "Low")
        close_col = cls._col(frame, "Close")
        adj_col = cls._col(frame, "Adj. Close", "Adjusted Close", "Adj Close")
        volume_col = cls._col(frame, "Volume")
        required = [date_col, open_col, high_col, low_col, close_col]
        if any(x is None for x in required):
            raise ValueError(f"Unexpected SimFin price columns: {list(frame.columns)}")
        out: list[SourcePriceBar] = []
        for _, row in frame.iterrows():
            raw_close = float(row[close_col])
            adjusted = float(row[adj_col]) if adj_col and pd.notna(row[adj_col]) else raw_close
            out.append(SourcePriceBar(
                security_id=security_id, source="SIMFIN", source_symbol=source_symbol,
                trade_date=parse_date(row[date_col]), open=float(row[open_col]), high=float(row[high_col]),
                low=float(row[low_col]), raw_close=raw_close, adjusted_close=adjusted,
                volume=float(row[volume_col]) if volume_col and pd.notna(row[volume_col]) else 0.0,
                retrieved_at=retrieved_at, quality_status=PriceQualityStatus.SECONDARY,
                adjustment_status=(AdjustmentStatus.DUAL_RAW_ADJUSTED if adj_col else AdjustmentStatus.RAW_ONLY),
                raw_payload_hash=sha256_payload(row.to_dict()),
            ))
        return sorted(out, key=lambda b: b.trade_date)

    async def get_daily_bar(self, security: Security, trade_date: date) -> SourcePriceBar | None:
        rows = await self.get_history(security, trade_date, trade_date)
        return rows[0] if rows else None

    async def get_market_snapshot(self, security: Security) -> MarketSnapshot | None:
        frame = self._load()
        ticker_col = self._col(frame, "Ticker", "Symbol")
        date_col = self._col(frame, "Date")
        if not ticker_col or not date_col:
            return None
        subset = frame[frame[ticker_col].astype(str).str.upper() == security.ticker.upper()].copy()
        if subset.empty:
            return None
        subset[date_col] = pd.to_datetime(subset[date_col])
        row = subset.sort_values(date_col).iloc[-1:]
        bars = self.parse_frame(security.security_id, security.ticker, row, retrieved_at=utc_now())
        if not bars:
            return None
        bar = bars[0]
        return MarketSnapshot(
            security_id=security.security_id, source=self.name, source_symbol=security.ticker,
            as_of=bar.retrieved_at, price=bar.adjusted_close, day_change_pct=None, volume=bar.volume,
            retrieved_at=bar.retrieved_at, quality_status=PriceQualityStatus.SECONDARY,
        )

    async def get_splits(self, security: Security, start: date | None = None, end: date | None = None) -> list[SplitEvent]:
        return []

    async def get_dividends(self, security: Security, start: date | None = None, end: date | None = None) -> list[DividendEvent]:
        return []

    async def validate_symbol(self, security: Security) -> bool:
        frame = self._load()
        ticker_col = self._col(frame, "Ticker", "Symbol")
        return bool(ticker_col and security.ticker.upper() in set(frame[ticker_col].astype(str).str.upper()))

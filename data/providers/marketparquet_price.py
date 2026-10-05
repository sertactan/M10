from __future__ import annotations

from datetime import date, datetime, timedelta
import re
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


class MarketParquetPriceProvider:
    name = "MARKETPARQUET"

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else None

    @property
    def configured(self) -> bool:
        return self.root is not None and self.root.exists()

    def _candidate_files(self, start: date, end: date) -> list[Path]:
        if not self.configured:
            raise RuntimeError("MARKETPARQUET_ROOT is not configured or missing")
        assert self.root is not None
        if self.root.is_file():
            return [self.root]
        out: list[Path] = []
        for path in self.root.rglob("*.parquet"):
            name = path.name
            match = re.search(r"(\d{4}-\d{2}-\d{2})", name)
            matched = False
            if match:
                try:
                    d = date.fromisoformat(match.group(1))
                    matched = start <= d <= end
                except ValueError:
                    matched = False
            if matched or (not match and "daily" in name.lower()):
                out.append(path)
        return sorted(set(out))

    @staticmethod
    def _find_col(frame: pd.DataFrame, *names: str) -> str | None:
        lowered = {str(c).lower(): str(c) for c in frame.columns}
        for n in names:
            if n.lower() in lowered:
                return lowered[n.lower()]
        return None

    async def get_history(self, security: Security, start: date, end: date) -> list[SourcePriceBar]:
        frames: list[pd.DataFrame] = []
        for path in self._candidate_files(start, end):
            frame = pd.read_parquet(path)
            frames.append(frame)
        if not frames:
            return []
        frame = pd.concat(frames, ignore_index=True)
        return self.parse_frame(security.security_id, security.ticker, frame, start, end, retrieved_at=utc_now())

    @classmethod
    def parse_frame(
        cls,
        security_id: str,
        ticker: str,
        frame: pd.DataFrame,
        start: date,
        end: date,
        *,
        retrieved_at: datetime,
    ) -> list[SourcePriceBar]:
        if frame.empty:
            return []
        symbol_col = cls._find_col(frame, "symbol", "ticker")
        date_col = cls._find_col(frame, "date", "timestamp")
        open_col = cls._find_col(frame, "open")
        high_col = cls._find_col(frame, "high")
        low_col = cls._find_col(frame, "low")
        close_col = cls._find_col(frame, "close")
        volume_col = cls._find_col(frame, "volume")
        if not all([symbol_col, date_col, open_col, high_col, low_col, close_col]):
            raise ValueError(f"Unexpected MarketParquet columns: {list(frame.columns)}")
        symbols = frame[symbol_col].astype(str).str.upper()
        accepted = {ticker.upper(), ticker.upper() + "-DELISTED"}
        subset = frame[symbols.isin(accepted)].copy()
        subset[date_col] = pd.to_datetime(subset[date_col]).dt.date
        subset = subset[(subset[date_col] >= start) & (subset[date_col] <= end)]
        out: list[SourcePriceBar] = []
        for _, row in subset.iterrows():
            close = float(row[close_col])
            source_symbol = str(row[symbol_col])
            out.append(SourcePriceBar(
                security_id=security_id, source="MARKETPARQUET", source_symbol=source_symbol,
                trade_date=parse_date(row[date_col]), open=float(row[open_col]), high=float(row[high_col]),
                low=float(row[low_col]), raw_close=close, adjusted_close=close,
                volume=float(row[volume_col]) if volume_col and pd.notna(row[volume_col]) else 0.0,
                retrieved_at=retrieved_at, quality_status=PriceQualityStatus.SURVIVORSHIP_AWARE,
                adjustment_status=AdjustmentStatus.ADJUSTED_ONLY,
                raw_payload_hash=sha256_payload(row.to_dict()),
            ))
        return sorted(out, key=lambda b: b.trade_date)

    async def get_daily_bar(self, security: Security, trade_date: date) -> SourcePriceBar | None:
        rows = await self.get_history(security, trade_date, trade_date)
        return rows[0] if rows else None

    async def get_market_snapshot(self, security: Security) -> MarketSnapshot | None:
        if not self.configured:
            return None
        rows = await self.get_history(security, date.today() - timedelta(days=15), date.today())
        if not rows:
            return None
        bar = rows[-1]
        return MarketSnapshot(
            security_id=security.security_id, source=self.name, source_symbol=bar.source_symbol,
            as_of=bar.retrieved_at, price=bar.adjusted_close, day_change_pct=None, volume=bar.volume,
            retrieved_at=bar.retrieved_at, quality_status=PriceQualityStatus.SURVIVORSHIP_AWARE,
        )

    async def get_splits(self, security: Security, start: date | None = None, end: date | None = None) -> list[SplitEvent]:
        return []

    async def get_dividends(self, security: Security, start: date | None = None, end: date | None = None) -> list[DividendEvent]:
        return []

    async def validate_symbol(self, security: Security) -> bool:
        try:
            return bool(await self.get_history(security, date.today() - timedelta(days=370), date.today()))
        except Exception:
            return False

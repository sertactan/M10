from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from core.optimization.cache import BoundedLRUCache
from core.prices.models import SourcePriceBar


class ParquetUnavailable(RuntimeError):
    pass


REQUIRED_PRICE_COLUMNS = [
    "security_id",
    "source",
    "source_symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "raw_close",
    "adjusted_close",
    "volume",
    "vwap",
    "retrieved_at",
    "quality_status",
    "adjustment_status",
    "raw_payload_hash",
]


class ParquetPriceStore:
    def __init__(self, root: str | Path, *, cache_capacity: int = 16) -> None:
        self.root = Path(root)
        self._read_cache = BoundedLRUCache(capacity=cache_capacity)

    @staticmethod
    def bars_to_frame(bars: list[SourcePriceBar]) -> pd.DataFrame:
        rows = []
        for b in bars:
            rows.append({
                "security_id": b.security_id,
                "source": b.source,
                "source_symbol": b.source_symbol,
                "trade_date": b.trade_date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "raw_close": b.raw_close,
                "adjusted_close": b.adjusted_close,
                "volume": b.volume,
                "vwap": b.vwap,
                "retrieved_at": b.retrieved_at,
                "quality_status": b.quality_status.value,
                "adjustment_status": b.adjustment_status.value,
                "raw_payload_hash": b.raw_payload_hash,
            })
        return pd.DataFrame(rows, columns=REQUIRED_PRICE_COLUMNS)

    @staticmethod
    def content_hash(frame: pd.DataFrame) -> str:
        if frame.empty:
            return hashlib.sha256(b"").hexdigest()
        stable = frame.copy()
        stable["trade_date"] = stable["trade_date"].astype(str)
        stable["retrieved_at"] = stable["retrieved_at"].astype(str)
        stable = stable.sort_values(["trade_date", "source", "source_symbol"]).reset_index(drop=True)
        payload = stable.to_csv(index=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _safe_partition(value: str) -> str:
        return (
            value.replace("/", "_")
            .replace("\\", "_")
            .replace("=", "_")
            .replace(":", "_")
        )

    def _year_path(
        self, source: str, security_id: str, source_symbol: str, year: int
    ) -> Path:
        return (
            self.root
            / "prices"
            / f"source={self._safe_partition(source)}"
            / f"security_id={self._safe_partition(security_id)}"
            / f"source_symbol={self._safe_partition(source_symbol)}"
            / f"year={year}"
            / "bars.parquet"
        )

    def write_bars(self, bars: list[SourcePriceBar]) -> list[Path]:
        if not bars:
            return []
        self._read_cache.clear()
        frame = self.bars_to_frame(bars)
        frame["year"] = pd.to_datetime(frame["trade_date"]).dt.year
        written: list[Path] = []
        for year, part in frame.groupby("year"):
            part = part.drop(columns=["year"])
            source = str(part.iloc[0]["source"])
            security_id = str(part.iloc[0]["security_id"])
            source_symbol = str(part.iloc[0]["source_symbol"])
            path = self._year_path(source, security_id, source_symbol, int(year))
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                try:
                    old = pd.read_parquet(path)
                    part = pd.concat([old, part], ignore_index=True)
                except (ImportError, ModuleNotFoundError) as exc:
                    raise ParquetUnavailable("Install pyarrow or fastparquet to use historical storage") from exc
            part = (
                part.sort_values(["trade_date", "retrieved_at"])
                .drop_duplicates(["trade_date", "source", "source_symbol"], keep="last")
            )
            temp_path = path.with_suffix(".tmp.parquet")
            try:
                part.to_parquet(temp_path, index=False)
                temp_path.replace(path)
            except (ImportError, ModuleNotFoundError) as exc:
                if temp_path.exists():
                    temp_path.unlink()
                raise ParquetUnavailable("Install pyarrow or fastparquet to use historical storage") from exc
            except Exception:
                if temp_path.exists():
                    temp_path.unlink()
                raise
            written.append(path)
        return written

    def read_bars(
        self,
        *,
        security_id: str,
        source: str,
        source_symbol: str,
        start_date,
        end_date,
    ) -> pd.DataFrame:
        year_paths: list[Path] = []
        signatures: list[tuple[str, int, int]] = []
        for year in range(start_date.year, end_date.year + 1):
            path = self._year_path(source, security_id, source_symbol, year)
            if path.exists():
                stat = path.stat()
                year_paths.append(path)
                signatures.append((str(path), stat.st_mtime_ns, stat.st_size))

        cache_key = (
            security_id,
            source,
            source_symbol,
            str(start_date),
            str(end_date),
            tuple(signatures),
        )
        cached = self._read_cache.get(cache_key)
        if cached is not None:
            return cached.copy(deep=True)

        frames: list[pd.DataFrame] = []
        for path in year_paths:
            try:
                frame = pd.read_parquet(
                    path,
                    columns=REQUIRED_PRICE_COLUMNS,
                    filters=[
                        ("trade_date", ">=", start_date),
                        ("trade_date", "<=", end_date),
                    ],
                )
            except (TypeError, ValueError, NotImplementedError):
                frame = pd.read_parquet(path, columns=REQUIRED_PRICE_COLUMNS)
            frames.append(frame)
        if not frames:
            result = pd.DataFrame(columns=REQUIRED_PRICE_COLUMNS)
            self._read_cache.put(cache_key, result)
            return result.copy(deep=True)

        frame = pd.concat(frames, ignore_index=True)
        dates = pd.to_datetime(frame["trade_date"]).dt.date
        result = frame[(dates >= start_date) & (dates <= end_date)].sort_values("trade_date")
        self._read_cache.put(cache_key, result.copy(deep=True))
        return result.copy(deep=True)

    @property
    def cache_stats(self):
        return self._read_cache.stats

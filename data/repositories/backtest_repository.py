from __future__ import annotations

from datetime import date, datetime

from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
from data.database.sqlite_store import SQLiteStore
from data.storage.parquet_price_store import ParquetPriceStore


class CanonicalBacktestPriceUnavailable(RuntimeError):
    pass


class BacktestRepository:
    """Read Phase 6 price inputs only from a prior canonical Phase 2 selection."""

    def __init__(self, store: SQLiteStore, parquet: ParquetPriceStore) -> None:
        self.store = store
        self.parquet = parquet

    def load_canonical_price_path(
        self,
        *,
        security_id: str,
        anchor_date: date,
        purpose: str = "BACKTEST",
    ) -> list[SourcePriceBar]:
        selection = self.store.connection.execute(
            """
            SELECT *
            FROM canonical_price_selection
            WHERE security_id=?
              AND purpose=?
              AND start_date<=?
              AND end_date>=?
            ORDER BY selected_at DESC
            LIMIT 1
            """,
            (security_id, purpose, anchor_date.isoformat(), anchor_date.isoformat()),
        ).fetchone()
        if selection is None:
            raise CanonicalBacktestPriceUnavailable(
                "No canonical Phase 2 price selection covers the requested anchor"
            )

        start = date.fromisoformat(selection["start_date"])
        end = date.fromisoformat(selection["end_date"])
        frame = self.parquet.read_bars(
            security_id=security_id,
            source=selection["source"],
            source_symbol=selection["source_symbol"],
            start_date=start,
            end_date=end,
        )
        if frame.empty:
            raise CanonicalBacktestPriceUnavailable(
                "Canonical Phase 2 selection exists but its Parquet series is unavailable"
            )

        bars: list[SourcePriceBar] = []
        for row in frame.to_dict(orient="records"):
            trade_date = row["trade_date"]
            if not isinstance(trade_date, date):
                trade_date = date.fromisoformat(str(trade_date)[:10])
            retrieved_at = row["retrieved_at"]
            if not isinstance(retrieved_at, datetime):
                retrieved_at = datetime.fromisoformat(str(retrieved_at))
            bars.append(
                SourcePriceBar(
                    security_id=str(row["security_id"]),
                    source=str(row["source"]),
                    source_symbol=str(row["source_symbol"]),
                    trade_date=trade_date,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    raw_close=float(row["raw_close"]),
                    adjusted_close=float(row["adjusted_close"]),
                    volume=float(row["volume"]),
                    vwap=float(row["vwap"]) if row.get("vwap") is not None else None,
                    retrieved_at=retrieved_at,
                    quality_status=PriceQualityStatus(str(row["quality_status"])),
                    adjustment_status=AdjustmentStatus(str(row["adjustment_status"])),
                    raw_payload_hash=(
                        str(row["raw_payload_hash"])
                        if row.get("raw_payload_hash") is not None
                        else None
                    ),
                )
            )
        return sorted(bars, key=lambda bar: bar.trade_date)

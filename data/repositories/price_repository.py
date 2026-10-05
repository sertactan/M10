from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from core.prices.models import DividendEvent, PriceSeriesDescriptor, SourcePriceBar, SplitEvent
from data.database.sqlite_store import SQLiteStore
from data.storage.parquet_price_store import ParquetPriceStore


class PriceRepository:
    def __init__(self, store: SQLiteStore, parquet: ParquetPriceStore) -> None:
        self.store = store
        self.parquet = parquet

    def save_series(self, bars: list[SourcePriceBar]) -> PriceSeriesDescriptor:
        if not bars:
            raise ValueError("Cannot save an empty price series")
        keys = {(b.security_id, b.source, b.source_symbol) for b in bars}
        if len(keys) != 1:
            raise ValueError(f"One registry series must have one identity/source/symbol: {keys}")
        security_id, source, source_symbol = next(iter(keys))
        ordered = sorted(bars, key=lambda b: b.trade_date)
        self.parquet.write_bars(ordered)
        frame = self.parquet.bars_to_frame(ordered)
        content_hash = self.parquet.content_hash(frame)
        descriptor = PriceSeriesDescriptor(
            security_id=security_id,
            source=source,
            source_symbol=source_symbol,
            start_date=ordered[0].trade_date,
            end_date=ordered[-1].trade_date,
            row_count=len(ordered),
            quality_status=ordered[0].quality_status,
            adjustment_status=ordered[0].adjustment_status,
            retrieved_at=max(b.retrieved_at for b in ordered),
            content_hash=content_hash,
        )
        series_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{security_id}|{source}|{source_symbol}"))
        self.store.connection.execute(
            """
            INSERT INTO price_series_registry (
                series_id,security_id,source,source_symbol,start_date,end_date,row_count,
                quality_status,adjustment_status,retrieved_at,content_hash,parquet_root,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(series_id) DO UPDATE SET
                start_date=MIN(price_series_registry.start_date,excluded.start_date),
                end_date=MAX(price_series_registry.end_date,excluded.end_date),
                row_count=MAX(price_series_registry.row_count,excluded.row_count),
                quality_status=excluded.quality_status,
                adjustment_status=excluded.adjustment_status,
                retrieved_at=excluded.retrieved_at,
                content_hash=excluded.content_hash,
                parquet_root=excluded.parquet_root,
                updated_at=excluded.updated_at
            """,
            (
                series_id, security_id, source, source_symbol, descriptor.start_date.isoformat(),
                descriptor.end_date.isoformat(), descriptor.row_count, descriptor.quality_status.value,
                descriptor.adjustment_status.value, descriptor.retrieved_at.astimezone(timezone.utc).isoformat(),
                descriptor.content_hash, str(self.parquet.root), datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return descriptor

    def series_for_window(self, security_id: str, start: date, end: date) -> list[PriceSeriesDescriptor]:
        rows = self.store.connection.execute(
            """
            SELECT * FROM price_series_registry
            WHERE security_id=? AND start_date<=? AND end_date>=?
            ORDER BY source
            """,
            (security_id, start.isoformat(), end.isoformat()),
        ).fetchall()
        from core.prices.models import AdjustmentStatus, PriceQualityStatus
        out=[]
        for r in rows:
            out.append(PriceSeriesDescriptor(
                security_id=r["security_id"], source=r["source"], source_symbol=r["source_symbol"],
                start_date=date.fromisoformat(r["start_date"]), end_date=date.fromisoformat(r["end_date"]),
                row_count=int(r["row_count"]), quality_status=PriceQualityStatus(r["quality_status"]),
                adjustment_status=AdjustmentStatus(r["adjustment_status"]),
                retrieved_at=datetime.fromisoformat(r["retrieved_at"]), content_hash=r["content_hash"],
            ))
        return out

    def select_series(
        self,
        *,
        security_id: str,
        start: date,
        end: date,
        source: str,
        source_symbol: str,
        purpose: str,
        reason: str,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO canonical_price_selection (
                selection_id,security_id,purpose,start_date,end_date,source,source_symbol,reason,selected_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()), security_id, purpose, start.isoformat(), end.isoformat(), source,
                source_symbol, reason, datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()

    def save_splits(self, events: list[SplitEvent]) -> int:
        for e in events:
            event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"split|{e.security_id}|{e.source}|{e.source_symbol}|{e.execution_date}|{e.split_from}|{e.split_to}"))
            self.store.connection.execute(
                """
                INSERT OR REPLACE INTO split_events_source (
                    event_id,security_id,source,source_symbol,execution_date,split_from,split_to,
                    retrieved_at,quality_status
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (event_id,e.security_id,e.source,e.source_symbol,e.execution_date.isoformat(),e.split_from,e.split_to,e.retrieved_at.isoformat(),e.quality_status.value),
            )
        self.store.connection.commit()
        return len(events)

    def save_dividends(self, events: list[DividendEvent]) -> int:
        for e in events:
            event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"div|{e.security_id}|{e.source}|{e.source_symbol}|{e.ex_date}|{e.cash_amount}"))
            self.store.connection.execute(
                """
                INSERT OR REPLACE INTO dividend_events_source (
                    event_id,security_id,source,source_symbol,ex_date,cash_amount,currency,
                    declaration_date,record_date,pay_date,retrieved_at,quality_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (event_id,e.security_id,e.source,e.source_symbol,e.ex_date.isoformat(),e.cash_amount,e.currency,
                 e.declaration_date.isoformat() if e.declaration_date else None,
                 e.record_date.isoformat() if e.record_date else None,
                 e.pay_date.isoformat() if e.pay_date else None,
                 e.retrieved_at.isoformat(),e.quality_status.value),
            )
        self.store.connection.commit()
        return len(events)

    def save_validation(
        self,
        *,
        security_id: str,
        start: date,
        end: date,
        source_a: str,
        source_b: str,
        overlap_rows: int,
        median_abs_pct_diff: float | None,
        max_abs_pct_diff: float | None,
        status: str,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO price_validation_results (
                validation_id,security_id,start_date,end_date,source_a,source_b,overlap_rows,
                median_abs_pct_diff,max_abs_pct_diff,status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (str(uuid.uuid4()),security_id,start.isoformat(),end.isoformat(),source_a,source_b,overlap_rows,
             median_abs_pct_diff,max_abs_pct_diff,status,datetime.now(timezone.utc).isoformat()),
        )
        self.store.connection.commit()

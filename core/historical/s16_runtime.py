from __future__ import annotations

from datetime import date, datetime

from core.prices.models import (
    AdjustmentStatus,
    PriceQualityStatus,
    SourcePriceBar,
)
from core.prices.policy import DEFAULT_PROVIDER_PRIORITY
from data.storage.parquet_price_store import ParquetPriceStore


def resolve_security_id(connection, *, ticker: str, as_of_date: date) -> str | None:
    ticker = ticker.upper()
    row = connection.execute(
        """
        SELECT security_id
        FROM ticker_aliases
        WHERE alias=?
          AND (valid_from='' OR valid_from<=?)
          AND (valid_to IS NULL OR valid_to='' OR valid_to>=?)
        ORDER BY CASE source WHEN 'MASSIVE' THEN 0 WHEN 'SEC_EDGAR' THEN 1 ELSE 9 END
        LIMIT 1
        """,
        (ticker, as_of_date.isoformat(), as_of_date.isoformat()),
    ).fetchone()
    if row is not None:
        return str(row["security_id"])
    row = connection.execute(
        """
        SELECT security_id FROM security_master
        WHERE ticker=?
        ORDER BY active DESC, updated_at DESC
        LIMIT 1
        """,
        (ticker,),
    ).fetchone()
    return str(row["security_id"]) if row is not None else None


def select_adjusted_series(
    connection,
    *,
    security_id: str,
    start_date: date,
    end_date: date,
    require_full_window: bool = True,
) -> dict | None:
    if require_full_window:
        window_sql = "start_date<=? AND end_date>=?"
        params = (security_id, start_date.isoformat(), end_date.isoformat())
    else:
        window_sql = "end_date>=? AND start_date<=?"
        params = (security_id, start_date.isoformat(), end_date.isoformat())

    rows = connection.execute(
        f"""
        SELECT *
        FROM price_series_registry
        WHERE security_id=?
          AND {window_sql}
          AND adjustment_status NOT IN ('RAW_ONLY','UNKNOWN')
          AND quality_status<>'FALLBACK_ONLY'
        """,
        params,
    ).fetchall()
    if not rows:
        return None
    rank = {name: i for i, name in enumerate(DEFAULT_PROVIDER_PRIORITY)}
    items = [dict(row) for row in rows]
    items.sort(
        key=lambda row: (
            rank.get(str(row["source"]), 999),
            -int(row["row_count"]),
        )
    )
    return items[0]


def load_source_bars(
    parquet: ParquetPriceStore,
    *,
    series: dict,
    start_date: date,
    end_date: date,
) -> list[SourcePriceBar]:
    frame = parquet.read_bars(
        security_id=str(series["security_id"]),
        source=str(series["source"]),
        source_symbol=str(series["source_symbol"]),
        start_date=start_date,
        end_date=end_date,
    )
    bars: list[SourcePriceBar] = []
    for row in frame.to_dict(orient="records"):
        trade_date = row["trade_date"]
        if not isinstance(trade_date, date):
            trade_date = date.fromisoformat(str(trade_date)[:10])
        retrieved_at = row["retrieved_at"]
        if not isinstance(retrieved_at, datetime):
            retrieved_at = datetime.fromisoformat(str(retrieved_at))
        bars.append(SourcePriceBar(
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
            vwap=(float(row["vwap"]) if row.get("vwap") is not None else None),
            retrieved_at=retrieved_at,
            quality_status=PriceQualityStatus(str(row["quality_status"])),
            adjustment_status=AdjustmentStatus(str(row["adjustment_status"])),
            raw_payload_hash=(
                str(row["raw_payload_hash"])
                if row.get("raw_payload_hash") is not None
                else None
            ),
        ))
    return sorted(bars, key=lambda bar: bar.trade_date)

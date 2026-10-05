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


    @staticmethod
    def _stable_json(value) -> str:
        import json
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def save_forward_outcome(self, outcome) -> str:
        import hashlib
        from datetime import datetime, timezone

        observation_id = f"{outcome.security_id}|{outcome.as_of_date_requested.isoformat()}"
        payload = {
            "observation_id": observation_id,
            "security_id": outcome.security_id,
            "as_of_date_requested": outcome.as_of_date_requested.isoformat(),
            "anchor_session": outcome.anchor_session.isoformat() if outcome.anchor_session else None,
            "anchor_lag_calendar_days": outcome.anchor_lag_calendar_days,
            "entry_adjusted_close": outcome.entry_adjusted_close,
            "horizon_sessions_available": outcome.horizon_sessions_available,
            "fm252": outcome.fm252,
            "max_multiple_observed": outcome.max_multiple_observed,
            "outcome_class": outcome.outcome_class,
            "time_to_2x_sessions": outcome.time_to_2x_sessions,
            "time_to_3x_sessions": outcome.time_to_3x_sessions,
            "time_to_5x_sessions": outcome.time_to_5x_sessions,
            "time_to_7x_sessions": outcome.time_to_7x_sessions,
            "time_to_10x_sessions": outcome.time_to_10x_sessions,
            "outcome_status": outcome.outcome_status,
            "diagnostics": dict(outcome.diagnostics),
        }
        outcome_hash = hashlib.sha256(
            self._stable_json(payload).encode("utf-8")
        ).hexdigest()
        self.store.connection.execute(
            """
            INSERT INTO forward_outcomes (
                observation_id,security_id,as_of_date_requested,anchor_session,
                anchor_lag_calendar_days,entry_adjusted_close,horizon_sessions_available,
                fm252,max_multiple_observed,outcome_class,time_to_2x_sessions,
                time_to_3x_sessions,time_to_5x_sessions,time_to_7x_sessions,
                time_to_10x_sessions,outcome_status,diagnostics_json,outcome_hash,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(observation_id) DO UPDATE SET
                anchor_session=excluded.anchor_session,
                anchor_lag_calendar_days=excluded.anchor_lag_calendar_days,
                entry_adjusted_close=excluded.entry_adjusted_close,
                horizon_sessions_available=excluded.horizon_sessions_available,
                fm252=excluded.fm252,
                max_multiple_observed=excluded.max_multiple_observed,
                outcome_class=excluded.outcome_class,
                time_to_2x_sessions=excluded.time_to_2x_sessions,
                time_to_3x_sessions=excluded.time_to_3x_sessions,
                time_to_5x_sessions=excluded.time_to_5x_sessions,
                time_to_7x_sessions=excluded.time_to_7x_sessions,
                time_to_10x_sessions=excluded.time_to_10x_sessions,
                outcome_status=excluded.outcome_status,
                diagnostics_json=excluded.diagnostics_json,
                outcome_hash=excluded.outcome_hash,
                created_at=excluded.created_at
            """,
            (
                observation_id,
                outcome.security_id,
                outcome.as_of_date_requested.isoformat(),
                outcome.anchor_session.isoformat() if outcome.anchor_session else None,
                outcome.anchor_lag_calendar_days,
                outcome.entry_adjusted_close,
                outcome.horizon_sessions_available,
                outcome.fm252,
                outcome.max_multiple_observed,
                outcome.outcome_class,
                outcome.time_to_2x_sessions,
                outcome.time_to_3x_sessions,
                outcome.time_to_5x_sessions,
                outcome.time_to_7x_sessions,
                outcome.time_to_10x_sessions,
                outcome.outcome_status,
                self._stable_json(dict(outcome.diagnostics)),
                outcome_hash,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return outcome_hash

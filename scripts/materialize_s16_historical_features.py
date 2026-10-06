from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import pstdev

from core.historical.s16_reconstruction import (
    S16HistoricalFeatureReconstructor,
    S16RawHistoricalObservation,
)
from core.historical.s16_runtime import select_adjusted_series
from data.database.sqlite_store import SQLiteStore
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.s16_evidence_repository import S16EvidenceRepository
from data.storage.parquet_price_store import ParquetPriceStore


def _read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"security_id", "ticker", "as_of_date", "float_shares"}
    if not rows:
        raise RuntimeError("S16 observation manifest is empty")
    missing = required - set(rows[0])
    if missing:
        raise RuntimeError("manifest missing columns: " + ", ".join(sorted(missing)))
    return rows


def _vol(values: list[float]) -> float:
    if len(values) < 3:
        raise ValueError("volatility requires >=3 closes")
    returns = [
        math.log(values[i] / values[i - 1])
        for i in range(1, len(values))
        if values[i - 1] > 0 and values[i] > 0
    ]
    if len(returns) < 2:
        raise ValueError("insufficient log returns")
    return pstdev(returns)


def _raw_from_price_frame(
    row: dict[str, str],
    *,
    as_of: datetime,
    frame,
) -> S16RawHistoricalObservation:
    frame = frame.sort_values("trade_date")
    dates = frame["trade_date"].astype(str).str[:10]
    frame = frame[dates <= as_of.date().isoformat()].tail(61)
    if len(frame) < 61:
        raise RuntimeError(
            f"{row['ticker']} {as_of.date()}: need 61 sessions, got {len(frame)}"
        )
    closes = [float(x) for x in frame["adjusted_close"]]
    volumes = [float(x) for x in frame["volume"]]
    if any(value <= 0 for value in closes):
        raise RuntimeError(f"{row['ticker']} {as_of.date()}: non-positive adjusted close")

    price = closes[-1]
    return_1d = price / closes[-2] - 1.0
    momentum5 = price / closes[-6] - 1.0
    momentum20 = price / closes[-21] - 1.0
    avg_volume20 = sum(volumes[-21:-1]) / 20.0
    if avg_volume20 <= 0:
        raise RuntimeError(f"{row['ticker']} {as_of.date()}: non-positive ADV20")

    prev5_volume = sum(volumes[-6:-1]) / 5.0
    volume_acceleration_raw = (
        volumes[-1] / prev5_volume if prev5_volume > 0 else 0.0
    )

    highs = [float(x) for x in frame["high"]]
    lows = [float(x) for x in frame["low"]]
    raw_closes = [float(x) for x in frame["raw_close"]]
    range_pcts = [
        ((high - low) / close if close > 0 and high >= low else 0.0)
        for high, low, close in zip(highs, lows, raw_closes)
    ]
    prior20_range = sum(range_pcts[-21:-1]) / 20.0
    range_expansion_raw = (
        range_pcts[-1] / prior20_range if prior20_range > 0 else 0.0
    )
    day_range = highs[-1] - lows[-1]
    close_location_raw = (
        min(1.0, max(0.0, (raw_closes[-1] - lows[-1]) / day_range))
        if day_range > 0 else 0.5
    )

    return S16RawHistoricalObservation(
        security_id=row["security_id"],
        ticker=row["ticker"].upper(),
        as_of=as_of,
        float_shares=float(row["float_shares"]),
        price=price,
        last_volume=volumes[-1],
        avg_volume20=avg_volume20,
        volatility10=_vol(closes[-11:]),
        volatility20=_vol(closes[-21:]),
        volatility60=_vol(closes[-61:]),
        return_1d=return_1d,
        momentum5=momentum5,
        momentum20=momentum20,
        volume_acceleration_raw=volume_acceleration_raw,
        range_expansion_raw=range_expansion_raw,
        close_location_raw=close_location_raw,
        supply_kind=row.get("supply_kind") or "UNKNOWN_SUPPLY",
        source_quality=row.get("source_quality") or "PIT_PROXY",
        market_cap=(
            float(row["market_cap"])
            if row.get("market_cap") not in (None, "")
            else None
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--parquet-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    store = SQLiteStore(args.db)
    store.initialize()
    parquet = ParquetPriceStore(args.parquet_root)
    evidence_repo = S16EvidenceRepository(store)
    reconstructor = S16HistoricalFeatureReconstructor(evidence_repo)
    model_features = ModelFeatureRepository(store)

    manifest = _read_manifest(args.manifest)
    by_date: dict[date, list[dict[str, str]]] = defaultdict(list)
    for row in manifest:
        by_date[date.fromisoformat(row["as_of_date"])].append(row)

    output: list[dict[str, object]] = []
    failures: list[str] = []

    for as_of_date, date_rows in sorted(by_date.items()):
        as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        raw_rows: list[S16RawHistoricalObservation] = []
        raw_manifest: dict[str, dict[str, str]] = {}

        for row in date_rows:
            start = as_of_date - timedelta(days=120)
            series = select_adjusted_series(
                store.connection,
                security_id=row["security_id"],
                start_date=start,
                end_date=as_of_date,
                require_full_window=True,
            )
            if series is None:
                failures.append(
                    f"{row['ticker']} {as_of_date}: no adjusted single-provider 120d series"
                )
                continue
            frame = parquet.read_bars(
                security_id=row["security_id"],
                source=str(series["source"]),
                source_symbol=str(series["source_symbol"]),
                start_date=start,
                end_date=as_of_date,
            )
            try:
                raw = _raw_from_price_frame(row, as_of=as_of, frame=frame)
            except Exception as exc:
                failures.append(str(exc))
                continue
            raw_rows.append(raw)
            raw_manifest[row["security_id"]] = row

        if not raw_rows:
            continue

        reconstructed = reconstructor.reconstruct_batch(raw_rows)
        for snapshot in reconstructed:
            row = raw_manifest[snapshot.security_id]
            payload: dict[str, object] = {
                "observation_id": row.get("observation_id") or (
                    f"{snapshot.security_id}|{as_of_date.isoformat()}"
                ),
                "cohort": row.get("cohort") or "",
                "security_id": snapshot.security_id,
                "ticker": snapshot.ticker,
                "as_of_date": as_of_date.isoformat(),
                "coverage_pct": f"{snapshot.coverage_pct:.6f}",
                "score_ready": str(snapshot.score_ready).lower(),
                "missing": ";".join(snapshot.missing),
            }
            for key, value in snapshot.features.items():
                payload[key] = "" if value is None else f"{float(value):.10f}"
                if args.persist and value is not None:
                    model_features.save_feature(
                        security_id=snapshot.security_id,
                        feature_key=f"S16::{key}",
                        value=float(value),
                        feature_as_of=snapshot.as_of,
                        available_at=snapshot.as_of,
                        source_phase="HISTORICAL_CONTROLS",
                        source_ref=f"S16_RECON:{snapshot.security_id}:{as_of_date.isoformat()}",
                        quality_status=(
                            "S16_PIT_COMPLETE" if snapshot.score_ready
                            else "S16_PIT_PARTIAL"
                        ),
                        computation_version=reconstructor.VERSION,
                        evidence=dict(snapshot.evidence),
                    )
            output.append(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not output:
        raise RuntimeError("no S16 historical feature rows materialized")
    fieldnames = list(output[0])
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)

    ready = sum(str(row["score_ready"]) == "true" for row in output)
    print(
        f"wrote {len(output)} S16 feature rows; score_ready={ready}; "
        f"price_failures={len(failures)}"
    )
    if failures:
        failures_path = args.output.with_suffix(".failures.txt")
        failures_path.write_text("\n".join(failures), encoding="utf-8")
        print(f"wrote failures to {failures_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

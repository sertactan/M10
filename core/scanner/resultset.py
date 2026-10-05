from __future__ import annotations

import csv
from dataclasses import fields
from pathlib import Path
from typing import Iterable

from core.scanner.contracts import ScanRow


SORTABLE_FIELDS = {
    "ticker",
    "exchange",
    "v12_score",
    "v14_score",
    "v12_status",
    "v14_status",
    "v12_route",
    "v14_route",
    "delisted",
}


def sort_rows(rows: Iterable[ScanRow], *, field: str, descending: bool = False) -> list[ScanRow]:
    if field not in SORTABLE_FIELDS:
        raise ValueError(f"unsupported sort field: {field}")

    def key(row: ScanRow):
        value = getattr(row, field)
        return (value is None, value)

    return sorted(rows, key=key, reverse=descending)


def filter_rows(
    rows: Iterable[ScanRow],
    *,
    exchanges: set[str] | None = None,
    min_v12_score: float | None = None,
    min_v14_score: float | None = None,
    include_delisted: bool = True,
) -> list[ScanRow]:
    out: list[ScanRow] = []
    for row in rows:
        if exchanges is not None and row.exchange not in exchanges:
            continue
        if min_v12_score is not None and (row.v12_score is None or row.v12_score < min_v12_score):
            continue
        if min_v14_score is not None and (row.v14_score is None or row.v14_score < min_v14_score):
            continue
        if not include_delisted and row.delisted:
            continue
        out.append(row)
    return out


def export_csv(rows: Iterable[ScanRow], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "security_id","ticker","exchange","as_of","mode",
        "v12_score","v12_status","v12_route","v12_destination",
        "v14_score","v14_status","v14_route","v14_destination","delisted",
    ]
    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "security_id": row.security_id,
                "ticker": row.ticker,
                "exchange": row.exchange,
                "as_of": row.as_of.isoformat(),
                "mode": row.mode.value,
                "v12_score": row.v12_score,
                "v12_status": row.v12_status,
                "v12_route": row.v12_route,
                "v12_destination": row.v12_destination,
                "v14_score": row.v14_score,
                "v14_status": row.v14_status,
                "v14_route": row.v14_route,
                "v14_destination": row.v14_destination,
                "delisted": row.delisted,
            })
    return destination

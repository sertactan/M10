"""Phase21: offline, read-only audit of an already lawfully downloaded SimFin US daily share-price CSV/ZIP.

NO HTTP/API calls, SQLite writes, automatic provider installation, canonical
price selection, data redistribution or backtest/model training. Input stays
private on Windows. This audit never certifies ticker -> historical SEC CIK.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import re
from typing import TextIO
import zipfile

from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider
from scripts.phase19_alpha_pit_staging import month_ends
from scripts.phase19_pit_source_audit import audit as audit_pit

SCHEMA = "MERIDYEN_PHASE21_FREE_SIMFIN_PRICE_AUDIT_V1"
PIT_SUCCESS = {
    "SOURCE_ARCHIVE_VERIFIED_NOT_PIT_CERTIFIED",
    "SOURCE_ARCHIVE_VERIFIED_WITH_IDENTITY_WARNINGS_NOT_PIT_CERTIFIED",
}
MAX_SOURCE_BYTES = 3 * 1024 ** 3
SAMPLES = 12


class PriceInputBlocked(ValueError):
    pass


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            data = source.read(4 * 1024 * 1024)
            if not data:
                break
            digest.update(data)
    return digest.hexdigest()


def _read_pit_symbols(pit_root: Path, start: date, end: date) -> set[str]:
    result = audit_pit(pit_root, start=start, end=end)
    if result["status"] not in PIT_SUCCESS:
        raise PriceInputBlocked("HISTORICAL_PIT_SOURCE_NOT_VERIFIED")
    symbols = set()
    for stamp in month_ends(start, end):
        with (pit_root / (stamp.isoformat() + ".csv")).open(
            "r", encoding="utf-8-sig", newline=""
        ) as source:
            for item in AlphaVantagePitUniverseProvider.parse_csv(
                source.read(), as_of=stamp
            ):
                symbols.add(item.ticker.upper())
    return symbols


def _reader(text: TextIO) -> csv.DictReader:
    header = text.readline()
    if not header:
        raise PriceInputBlocked("EMPTY_PRICE_SOURCE")
    # Official SimFin examples use ';'; manually exported CSV may use ','.
    delimiter = ";" if header.count(";") >= header.count(",") else ","
    return csv.DictReader(_stream_with_header(header, text), delimiter=delimiter)


def _stream_with_header(header: str, source: TextIO):
    yield header
    yield from source


def _one_price_stream(handle: TextIO, start: date, end: date,
                      pit_symbols: set[str]) -> dict:
    reader = _reader(handle)
    column_map = {c.strip().lower(): c for c in (reader.fieldnames or [])}
    def col(*names):
        return next((column_map[n.lower()] for n in names
                     if n.lower() in column_map), None)
    columns = {
        "ticker": col("Ticker", "Symbol"),
        "id": col("SimFinId", "Simfin ID", "SimFin Id"),
        "date": col("Date"),
        "open": col("Open"),
        "high": col("High"),
        "low": col("Low"),
        "close": col("Close"),
        "adjusted": col("Adj. Close", "Adjusted Close", "Adj Close"),
        "volume": col("Volume"),
    }
    missing = [k for k in ("ticker", "date", "open", "high", "low", "close")
               if columns[k] is None]
    if missing:
        raise PriceInputBlocked("PRICE_COLUMNS_MISSING_" + "_".join(missing).upper())
    totals = Counter()
    ticker_sessions = Counter()
    ticker_to_simfin_ids = defaultdict(set)
    period_symbols = set()
    source_earliest = None
    source_latest = None
    samples = []
    for item in reader:
        totals["total_rows"] += 1
        ticker = str(item.get(columns["ticker"], "") or "").strip().upper()
        ds = str(item.get(columns["date"], "") or "").strip()
        if not ticker or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ds):
            totals["rows_invalid_ticker_or_date"] += 1
            continue
        try:
            when = date.fromisoformat(ds)
        except ValueError:
            totals["rows_invalid_ticker_or_date"] += 1
            continue
        if source_earliest is None or when < source_earliest:
            source_earliest = when
        if source_latest is None or when > source_latest:
            source_latest = when
        if not start <= when <= end:
            continue
        totals["window_rows"] += 1
        period_symbols.add(ticker)
        sid = str(item.get(columns["id"], "") or "").strip() if columns["id"] else ""
        if sid:
            ticker_to_simfin_ids[ticker].add(sid)
        try:
            o, h, l, c = [float(item[columns[k]]) for k in
                          ("open", "high", "low", "close")]
            if not (0 < o <= h and 0 < c <= h and 0 < l <= min(o, c)):
                raise ValueError("OHLC_NOT_PLAUSIBLE")
        except (TypeError, ValueError):
            totals["window_invalid_ohlc_rows"] += 1
            if len(samples) < SAMPLES:
                samples.append({"ticker": ticker, "date": ds,
                                "issue": "INVALID_OHLC"})
            continue
        totals["window_valid_ohlc_rows"] += 1
        ticker_sessions[ticker] += 1
        if columns["adjusted"]:
            try:
                adjusted = float(item[columns["adjusted"]])
                if adjusted > 0 and adjusted < 1e9:
                    totals["window_adj_close_numeric_rows"] += 1
                else:
                    totals["window_missing_or_invalid_adjusted_rows"] += 1
            except (TypeError, ValueError):
                totals["window_missing_or_invalid_adjusted_rows"] += 1
        if columns["volume"]:
            try:
                if float(item[columns["volume"]]) >= 0:
                    totals["window_nonnegative_volume_rows"] += 1
            except (TypeError, ValueError):
                pass
    if not totals["total_rows"]:
        raise PriceInputBlocked("NO_SOURCE_PRICE_ROWS")
    in_pit = period_symbols & pit_symbols
    counts = {
        "all_source_rows": totals["total_rows"],
        "window_rows": totals["window_rows"],
        "window_valid_ohlc_rows": totals["window_valid_ohlc_rows"],
        "window_invalid_ohlc_rows": totals["window_invalid_ohlc_rows"],
        "period_unique_ticker_strings": len(period_symbols),
        "period_unique_tickers_also_in_21_month_PIT": len(in_pit),
        "period_unique_tickers_not_in_21_month_PIT": len(period_symbols - pit_symbols),
        "pit_distinct_tickers_without_price_rows": len(pit_symbols - period_symbols),
        "tickers_with_at_least_100_valid_price_rows": sum(
            n >= 100 for n in ticker_sessions.values()
        ),
        "tickers_with_at_least_300_valid_price_rows": sum(
            n >= 300 for n in ticker_sessions.values()
        ),
        "tickers_with_multiple_simfin_ids_in_window": sum(
            len(ids) > 1 for ids in ticker_to_simfin_ids.values()
        ),
        "ticker_id_ambiguity_examples": sorted(
            t for t, ids in ticker_to_simfin_ids.items() if len(ids) > 1
        )[:SAMPLES],
        "source_adjusted_close_column_present": bool(columns["adjusted"]),
        "window_valid_numeric_adj_close_rows":
            totals["window_adj_close_numeric_rows"],
        "window_missing_or_invalid_adjusted_rows":
            totals["window_missing_or_invalid_adjusted_rows"],
        "window_nonnegative_volume_rows": totals["window_nonnegative_volume_rows"],
        "earliest_date_in_source": str(source_earliest) if source_earliest else None,
        "latest_date_in_source": str(source_latest) if source_latest else None,
        "sample_invalid_ohlc": samples,
        "detected_columns": columns,
    }
    return counts


def analyze(input_file: Path, pit_root: Path, start: date, end: date) -> dict:
    if end < start:
        raise PriceInputBlocked("DATE_RANGE_INVALID")
    if input_file.is_symlink() or not input_file.is_file():
        raise PriceInputBlocked("PRICE_FILE_MISSING_OR_SYMLINK")
    if input_file.stat().st_size > MAX_SOURCE_BYTES:
        raise PriceInputBlocked("PRICE_SOURCE_OVER_3GIB")
    symbols = _read_pit_symbols(pit_root, start, end)
    sha = _file_sha256(input_file)
    if zipfile.is_zipfile(input_file):
        with zipfile.ZipFile(input_file) as archive:
            entries = [i for i in archive.infolist()
                       if not i.is_dir() and i.filename.lower().endswith((".csv", ".txt"))]
            if len(entries) != 1:
                raise PriceInputBlocked("ZIP_REQUIRES_EXACTLY_ONE_CSV_MEMBER")
            member = entries[0]
            if member.file_size > MAX_SOURCE_BYTES or member.flag_bits & 1:
                raise PriceInputBlocked("ZIP_ENTRY_TOO_LARGE_OR_ENCRYPTED")
            with archive.open(member) as binary:
                with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as handle:
                    counts = _one_price_stream(handle, start, end, symbols)
    else:
        if input_file.suffix.lower() not in (".csv", ".txt"):
            raise PriceInputBlocked("PRICE_INPUT_MUST_BE_CSV_OR_ZIP")
        with input_file.open("r", encoding="utf-8-sig", newline="") as handle:
            counts = _one_price_stream(handle, start, end, symbols)
    return {
        "schema": SCHEMA, "status": "SOURCE_COVERAGE_MEASURED_NOT_CANONICAL",
        "period": {"start": str(start), "end": str(end)},
        "source": "SIMFIN_USER_SUPPLIED_CSV_RESEARCH_ONLY",
        "original_file_sha256": sha,
        "input_bytes": input_file.stat().st_size,
        "hist_21_month_unique_ticker_strings": len(symbols),
        "source_counts": counts,
        "adjustment_provenance_independently_verified": False,
        "historical_security_cik_mapping_certified": False,
        "delisting_return_certified": False,
        "data_provider_usage_rights_confirmed_by_user": False,
        "canonical_price_selections_written": 0,
        "operational_database_modified": False,
        "model_training_performed": False,
        "paid_api_called": False,
        "network_calls": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True,
                   help="Local user-acquired SimFin daily US shareprices .csv or .zip")
    default = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime"
    )
    p.add_argument("--pit-dir", type=Path, default=default/"phase19/pit_staging")
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2025-09-30")
    p.add_argument("--out", type=Path,
                   default=default/"phase21/simfin_free_price_source_audit.json")
    args = p.parse_args()
    try:
        report = analyze(args.input, args.pit_dir, date.fromisoformat(args.start),
                         date.fromisoformat(args.end))
    except (PriceInputBlocked, OSError, ValueError, UnicodeError, zipfile.BadZipFile):
        print("PHASE21_BLOCKED: PRICE_SOURCE_OR_FORMAT_NOT_ACCEPTED")
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    part = args.out.with_suffix(args.out.suffix + ".tmp")
    part.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    part.replace(args.out)
    print(json.dumps({
        "status": report["status"], "source": report["source"],
        "source_counts": report["source_counts"],
        "full_report": str(args.out),
        "operational_database_modified": False,
        "canonical_price_selections_written": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

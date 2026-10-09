"""Phase22: offline SimFin OHLC diagnostics and calendar-month PIT-price overlap.

This is a RESEARCH-ONLY data quality / source-coverage check. Month-end
Alpha Vantage ticker presence is NOT daily PIT security identity; no automatic
ticker->CIK joining, adjusted-price certification or database writes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date
import json
import math
import os
from pathlib import Path
import re
import zipfile
import io

from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider
from scripts.phase19_alpha_pit_staging import month_ends
from scripts.phase19_pit_source_audit import audit as audit_pit
from scripts.phase21_simfin_price_source_audit import (
    PriceInputBlocked, _reader, _file_sha256, MAX_SOURCE_BYTES, PIT_SUCCESS,
)

SCHEMA = "MERIDYEN_PHASE22_SIMFIN_OHLC_MONTHLY_PIT_QA_V1"


@contextmanager
def input_text(path: Path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise PriceInputBlocked("SOURCE_FILE_NOT_SAFE")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            items = [i for i in archive.infolist()
                     if not i.is_dir() and i.filename.lower().endswith((".csv", ".txt"))]
            if len(items) != 1:
                raise PriceInputBlocked("SOURCE_ZIP_REQUIRE_ONE_CSV")
            entry = items[0]
            if entry.file_size > MAX_SOURCE_BYTES or entry.flag_bits & 1:
                raise PriceInputBlocked("SOURCE_ZIP_TOO_LARGE_OR_ENCRYPTED")
            with archive.open(entry) as raw:
                with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as handle:
                    yield handle
    else:
        if path.suffix.lower() not in (".csv", ".txt"):
            raise PriceInputBlocked("SOURCE_EXPECTED_CSV")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            yield handle


def _monthly_pit(pit_dir: Path, start: date, end: date) -> dict[str, set[str]]:
    source = audit_pit(pit_dir, start=start, end=end)
    if source["status"] not in PIT_SUCCESS:
        raise PriceInputBlocked("PHASE19_PIT_ARCHIVE_NOT_VERIFIED")
    result = {}
    for d in month_ends(start, end):
        name = d.isoformat()
        content = (pit_dir / (name + ".csv")).read_text(encoding="utf-8-sig")
        records = AlphaVantagePitUniverseProvider.parse_csv(content, as_of=d)
        result[name[:7]] = {r.ticker.upper() for r in records}
    return result


def _classify_ohlc(row: dict, cols: dict) -> str:
    try:
        o, h, l, c = (float(row[cols[n]]) for n in ("open", "high", "low", "close"))
    except (TypeError, ValueError, KeyError):
        return "NON_NUMERIC_OHLC"
    if not all(math.isfinite(p) for p in (o, h, l, c)):
        return "NON_FINITE_OHLC"
    if min(o, h, l, c) <= 0:
        return "NONPOSITIVE_OHLC"
    if l > h:
        return "LOW_EXCEEDS_HIGH"
    if not l <= o <= h:
        return "OPEN_OUTSIDE_RANGE"
    if not l <= c <= h:
        return "CLOSE_OUTSIDE_RANGE"
    return "VALID"


def analyze(path: Path, pit_dir: Path, phase21_report: Path,
            start: date, end: date) -> dict:
    if end < start:
        raise PriceInputBlocked("DATE_WINDOW_INVALID")
    membership = _monthly_pit(pit_dir, start, end)
    if not phase21_report.is_file() or phase21_report.is_symlink():
        raise PriceInputBlocked("PHASE21_REPORT_MISSING_OR_UNSAFE")
    old = json.loads(phase21_report.read_text(encoding="utf-8"))
    if old.get("schema") != "MERIDYEN_PHASE21_FREE_SIMFIN_PRICE_AUDIT_V1":
        raise PriceInputBlocked("PHASE21_REPORT_SCHEMA_MISMATCH")
    if old.get("period") != {"start": str(start), "end": str(end)}:
        raise PriceInputBlocked("PHASE21_WINDOW_MISMATCH")
    if old.get("original_file_sha256") != _file_sha256(path):
        raise PriceInputBlocked("PHASE21_PRICE_INPUT_HASH_MISMATCH")
    totals = Counter()
    reasons = Counter()
    by_month = defaultdict(Counter)
    per_month_pit_valid_symbols: dict[str, set[str]] = defaultdict(set)
    per_month_price_symbols: dict[str, set[str]] = defaultdict(set)
    valid_price_rows_pit_ever = Counter()
    valid_price_rows_month_listed = Counter()
    months_seen_with_prices = defaultdict(set)
    examples = []
    # Strictly stream: do NOT load 6 million price rows into memory.
    with input_text(path) as handle:
        csv = _reader(handle)
        cols = {key: next((col for col in csv.fieldnames or []
                           if str(col).strip().lower() in options), None)
                for key, options in {
                    "ticker": ("ticker", "symbol"), "date": ("date",),
                    "open": ("open",), "high": ("high",), "low": ("low",),
                    "close": ("close",), "adjusted": ("adj. close", "adjusted close", "adj close"),
                }.items()}
        if any(cols.get(x) is None for x in ("ticker", "date", "open", "high", "low", "close")):
            raise PriceInputBlocked("OHLC_SOURCE_COLUMNS_MISSING")
        all_pit_tickers = set().union(*membership.values())
        for row in csv:
            totals["all_rows"] += 1
            ticker = str(row.get(cols["ticker"]) or "").strip().upper()
            ds = str(row.get(cols["date"]) or "").strip()
            if not ticker or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ds):
                totals["invalid_date_or_ticker"] += 1
                continue
            try:
                trade_date = date.fromisoformat(ds)
            except ValueError:
                totals["invalid_date_or_ticker"] += 1
                continue
            if not start <= trade_date <= end:
                continue
            totals["window_rows"] += 1
            month = ds[:7]
            by_month[month]["rows"] += 1
            per_month_price_symbols[month].add(ticker)
            belongs_to_month_end_list = ticker in membership.get(month, set())
            if belongs_to_month_end_list:
                totals["window_rows_ticker_in_same_month_end_listing"] += 1
                by_month[month]["listed_ticker_rows"] += 1
            classification = _classify_ohlc(row, cols)
            if classification == "VALID":
                totals["window_valid_ohlc_rows"] += 1
                by_month[month]["valid_rows"] += 1
                if ticker in all_pit_tickers:
                    valid_price_rows_pit_ever[ticker] += 1
                if belongs_to_month_end_list:
                    valid_price_rows_month_listed[ticker] += 1
                    per_month_pit_valid_symbols[month].add(ticker)
                    months_seen_with_prices[ticker].add(month)
                if cols["adjusted"]:
                    try:
                        adj = float(row.get(cols["adjusted"]) or "")
                        if 0 < adj < 1e9 and math.isfinite(adj):
                            totals["window_valid_ohlc_positive_adj_rows"] += 1
                            if belongs_to_month_end_list:
                                totals["window_listed_ticker_valid_ohlc_positive_adj_rows"] += 1
                    except (ValueError, TypeError):
                        pass
            else:
                totals["window_invalid_ohlc_rows"] += 1
                reasons[classification] += 1
                by_month[month]["strict_ohlc_invalid_rows"] += 1
                if len(examples) < 25:
                    examples.append({"ticker":ticker,"date":ds,
                                     "reason":classification,
                                     "same_month_end_listed_ticker":belongs_to_month_end_list})
    expected = old["source_counts"]
    checks = {
        "all_source_rows": (totals["all_rows"], expected.get("all_source_rows")),
        "window_rows": (totals["window_rows"], expected.get("window_rows")),
        "window_valid_ohlc_rows": (
            totals["window_valid_ohlc_rows"], expected.get("window_valid_ohlc_rows")),
        "window_invalid_ohlc_rows": (
            totals["window_invalid_ohlc_rows"], expected.get("window_invalid_ohlc_rows")),
    }
    mismatches = [key for key,(actual,old_value) in checks.items()
                  if actual != old_value]
    if mismatches:
        raise PriceInputBlocked("PHASE21_COUNTS_DID_NOT_RECONCILE")
    month_rows = []
    for month in sorted(membership):
        listed = membership[month]
        matched = per_month_pit_valid_symbols[month]
        price_symbols = per_month_price_symbols[month]
        month_rows.append({
            "month":month,
            "month_end_listing_ticker_count":len(listed),
            "price_tickers_in_month":len(price_symbols),
            "listed_tickers_with_valid_prices_in_same_calendar_month":len(matched),
            "listed_tickers_without_valid_prices_in_same_calendar_month":
                len(listed - matched),
            "candidate_month_end_ticker_overlap_NOT_PIT_certification":
                len(listed & price_symbols),
            **dict(by_month[month]),
        })
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_ONLY_OHLC_CAUSE_AND_MONTHLY_PIT_PRICE_COVERAGE_AUDIT",
        "period":{"start":str(start),"end":str(end)},
        "verified_months":len(month_rows),
        "reconciled_phase21_counts":True,
        "original_price_file_sha256":old["original_file_sha256"],
        "window_rows":totals["window_rows"],
        "window_valid_ohlc_rows":totals["window_valid_ohlc_rows"],
        "window_strict_invalid_ohlc_rows":totals["window_invalid_ohlc_rows"],
        "invalid_ohlc_reason_counts":dict(sorted(reasons.items())),
        "sample_issue_ticker_date_only":examples,
        "window_rows_ticker_in_same_month_end_listing":
            totals["window_rows_ticker_in_same_month_end_listing"],
        "window_listed_ticker_valid_ohlc_positive_adj_rows":
            totals["window_listed_ticker_valid_ohlc_positive_adj_rows"],
        "pit_tickers_with_100_plus_valid_rows_any_month":
            sum(n>=100 for n in valid_price_rows_pit_ever.values()),
        "pit_tickers_with_300_plus_valid_rows_any_month":
            sum(n>=300 for n in valid_price_rows_pit_ever.values()),
        "pit_tickers_with_100_plus_valid_rows_in_listed_calendar_months":
            sum(n>=100 for n in valid_price_rows_month_listed.values()),
        "pit_tickers_with_300_plus_valid_rows_in_listed_calendar_months":
            sum(n>=300 for n in valid_price_rows_month_listed.values()),
        "per_month":month_rows,
        "ticker_year_month_overlap_is_historical_identity_proof":False,
        "free_source_adjustment_independently_certified":False,
        "delisting_returns_verified":False,
        "SEC_CIK_identity_verified":False,
        "canonical_prices_written":0,
        "production_database_modified":False,
        "model_training_performed":False,
        "network_requests":0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    default = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime"
    )
    p.add_argument("--pit-dir", type=Path, default=default/"phase19/pit_staging")
    p.add_argument("--phase21-report", type=Path,
                   default=default/"phase21/simfin_free_price_source_audit.json")
    p.add_argument("--out", type=Path,
                   default=default/"phase22/simfin_ohlc_monthly_coverage.json")
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2025-09-30")
    args = p.parse_args()
    try:
        report = analyze(args.input, args.pit_dir,args.phase21_report,
                         date.fromisoformat(args.start),date.fromisoformat(args.end))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        # Sensitive source filenames/paths and provider credentials are not logged.
        print("PHASE22_BLOCKED:", type(exc).__name__)
        return 2
    dest = args.out.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",
                    encoding="utf-8")
    temp.replace(dest)
    print(json.dumps({
        "status":report["status"],
        "verified_months":report["verified_months"],
        "reconciled_phase21_counts":report["reconciled_phase21_counts"],
        "invalid_ohlc_reason_counts":report["invalid_ohlc_reason_counts"],
        "window_rows_ticker_in_same_month_end_listing":
            report["window_rows_ticker_in_same_month_end_listing"],
        "window_listed_ticker_valid_ohlc_positive_adj_rows":
            report["window_listed_ticker_valid_ohlc_positive_adj_rows"],
        "pit_tickers_with_100_plus_valid_rows_in_listed_calendar_months":
            report["pit_tickers_with_100_plus_valid_rows_in_listed_calendar_months"],
        "pit_tickers_with_300_plus_valid_rows_in_listed_calendar_months":
            report["pit_tickers_with_300_plus_valid_rows_in_listed_calendar_months"],
        "per_month":report["per_month"],
        "report_file":str(dest),
        "production_database_modified":False,
        "canonical_prices_written":0,
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

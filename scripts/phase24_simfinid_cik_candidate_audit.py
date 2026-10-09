"""Phase24: SimFinId -> *candidate* SEC CIK, with strict historical identity gates.

Offline, source-SHA-verified, SQLite read-only. Never promotes candidates into
canonical PIT, never equates ticker text with historical issuer identity, and
never repairs/rewrites prices, SEC facts, or existing models.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import zipfile

from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider
from scripts.phase19_alpha_pit_staging import month_ends
from scripts.phase19_pit_source_audit import audit as audit_pit
from scripts.phase21_simfin_price_source_audit import (
    _file_sha256, _reader, PIT_SUCCESS, PriceInputBlocked,
)
from scripts.phase22_simfin_ohlc_monthly_qa import input_text, _classify_ohlc

SCHEMA = "MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1"
S21 = "MERIDYEN_PHASE21_FREE_SIMFIN_PRICE_AUDIT_V1"
S20 = "MERIDYEN_PHASE20_HISTORICAL_IDENTITY_CANDIDATES_V1"
S23 = "MERIDYEN_PHASE23_SIMFIN_NONPOSITIVE_OHLC_TRIAGE_V1"
DIRECT_TYPES = {"CURRENT_TICKER_EXCHANGE_CIK_CANDIDATE",
                "CURRENT_TICKER_EXCHANGE_NO_CIK"}


def _read_json(path: Path, expected_schema: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise PriceInputBlocked("PRIOR_AUDIT_REPORT_MISSING")
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("schema") != expected_schema:
        raise PriceInputBlocked("PRIOR_AUDIT_REPORT_SCHEMA_MISMATCH")
    return result


def _cik(raw: object) -> str | None:
    s = str(raw or "").strip()
    return s.zfill(10) if s.isdigit() and len(s) <= 10 and int(s) > 0 else None


def _candidate_index(db: Path, sid_set: set[str]) -> dict[str, dict]:
    if db.is_symlink() or not db.is_file():
        raise PriceInputBlocked("INSTALLED_DB_MISSING")
    con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro",
                          uri=True, timeout=30)
    try:
        con.execute("PRAGMA query_only=ON")
        cols = {r[1] for r in con.execute("PRAGMA table_info(security_master)")}
        if not {"security_id", "ticker", "exchange", "market", "cik"}.issubset(cols):
            raise PriceInputBlocked("SECURITY_MASTER_SCHEMA_MISSING")
        out = {}
        for sid, ticker, exchange, cik in con.execute(
            "SELECT security_id,ticker,exchange,cik FROM security_master WHERE market='US'"
        ):
            sid = str(sid)
            if sid in sid_set:
                out[sid] = {"security_id": sid,
                            "current_ticker": str(ticker or "").upper().strip(),
                            "current_exchange": str(exchange or "").upper().strip(),
                            "CIK_candidate": _cik(cik)}
        return out
    finally:
        con.close()


def _monthly_symbol_exchange(pit_root: Path, start: date,
                             end: date) -> dict[str, dict[str, set[str]]]:
    verified = audit_pit(pit_root, start=start, end=end)
    if verified["status"] not in PIT_SUCCESS:
        raise PriceInputBlocked("PIT_SOURCE_ARCHIVE_NOT_VERIFIED")
    by_month = {}
    for as_of in month_ends(start, end):
        txt = (pit_root / (as_of.isoformat() + ".csv")).read_text(encoding="utf-8-sig")
        records = AlphaVantagePitUniverseProvider.parse_csv(txt, as_of=as_of)
        mapping = defaultdict(set)
        for record in records:
            mapping[record.ticker.upper()].add(record.exchange.value)
        by_month[as_of.strftime("%Y-%m")] = dict(mapping)
    return by_month


def analyze(source: Path, pit_dir: Path, db: Path, phase20_file: Path,
            phase21_file: Path, phase23_file: Path) -> dict:
    phase20 = _read_json(phase20_file, S20)
    phase21 = _read_json(phase21_file, S21)
    phase23 = _read_json(phase23_file, S23)
    if (phase20.get("status") != "CANDIDATES_ONLY_HISTORICAL_IDENTITY_NOT_CERTIFIED"
        or phase20.get("months_verified") != 21
        or phase21.get("status") != "SOURCE_COVERAGE_MEASURED_NOT_CANONICAL"
        or phase23.get("status") != "RESEARCH_ONLY_NONPOSITIVE_OHLC_FIELD_CAUSES_MEASURED"
        or phase23.get("reconciled_against_phase22") is not True):
        raise PriceInputBlocked("PRIOR_SOURCE_AUDIT_NOT_READY")
    start = date.fromisoformat(phase21["period"]["start"])
    end = date.fromisoformat(phase21["period"]["end"])
    if phase23.get("period") != phase21.get("period"):
        raise PriceInputBlocked("AUDIT_PERIOD_MISMATCH")
    original_sha = _file_sha256(source)
    if (original_sha != phase21.get("original_file_sha256")
        or original_sha != phase23.get("source_file_sha256")):
        raise PriceInputBlocked("SIMFIN_ORIGINAL_PRICE_SOURCE_CHANGED")

    months = _monthly_symbol_exchange(pit_dir, start, end)
    by_listing = {}
    sid_set = set()
    for d in phase20.get("details", []):
        key = (d["ticker"].upper(), d["exchange"].upper())
        if key in by_listing:
            raise PriceInputBlocked("PHASE20_DUPLICATE_LISTING_KEY")
        by_listing[key] = d
        sid_set.update(str(c["security_id"])
                       for c in d.get("candidate_sample_not_certified", []))
    if len(by_listing) != phase20.get("distinct_ticker_exchange_listing_keys"):
        raise PriceInputBlocked("PHASE20_LISTING_COUNT_MISMATCH")
    historic_keys = set().union(*(
        {(t, e) for t, exchanges in m.items() for e in exchanges}
        for m in months.values()
    ))
    if historic_keys != set(by_listing):
        raise PriceInputBlocked("PHASE19_PHASE20_LISTING_KEY_MISMATCH")
    local_id = _candidate_index(db, sid_set)
    groups: dict[str, dict] = {}
    ticker_to_ids: dict[str, set[str]] = defaultdict(set)
    simfin_to_tickers: dict[str, set[str]] = defaultdict(set)
    overlap_ticker_strings = set()
    totals = Counter()
    all_historical_tickers = {ticker for ticker, _ in historic_keys}
    with input_text(source) as stream:
        reader = _reader(stream)
        col = {s.strip().lower(): s for s in (reader.fieldnames or [])}
        def get(*names):
            return next((col.get(x.lower()) for x in names
                         if col.get(x.lower())), None)
        columns = {"ticker": get("Ticker", "Symbol"), "id": get("SimFinId"),
                   "date": get("Date"), "adjusted": get("Adj. Close",
                   "Adjusted Close", "Adj Close")}
        columns.update({x: get(x) for x in ("open", "high", "low", "close")})
        if any(v is None for v in columns.values()):
            raise PriceInputBlocked("SIMFIN_ID_OR_PRICE_COLUMNS_MISSING")
        for row in reader:
            totals["all_rows"] += 1
            ticker = str(row.get(columns["ticker"]) or "").strip().upper()
            sid = str(row.get(columns["id"]) or "").strip()
            ds = str(row.get(columns["date"]) or "").strip()
            if not ticker or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ds):
                continue
            try:
                when = date.fromisoformat(ds)
            except ValueError:
                continue
            if not start <= when <= end:
                continue
            totals["window_rows"] += 1
            if ticker in all_historical_tickers:
                overlap_ticker_strings.add(ticker)
            if not sid:
                totals["window_rows_missing_simfin_id"] += 1
                continue
            ticker_to_ids[ticker].add(sid)
            simfin_to_tickers[sid].add(ticker)
            if sid not in groups:
                groups[sid] = {"SimFinId":sid,"first_date":ds,"last_date":ds,
                               "ticker_strings":set(),"months_with_price":set(),
                               "overlapping_months":set(),"months_multiple_list_exchanges":set(),
                               "window_rows":0,"valid_OHLC_rows":0,
                               "strict_invalid_OHLC_rows":0,
                               "matched_month_valid_OHLC_adj_rows":0}
            g = groups[sid]
            g["ticker_strings"].add(ticker)
            g["months_with_price"].add(ds[:7])
            g["window_rows"] += 1
            g["first_date"] = min(g["first_date"],ds)
            g["last_date"] = max(g["last_date"],ds)
            is_listed_in_month = ticker in months.get(ds[:7], {})
            if is_listed_in_month:
                g["overlapping_months"].add(ds[:7])
                if len(months[ds[:7]][ticker]) > 1:
                    g["months_multiple_list_exchanges"].add(ds[:7])
            reason = _classify_ohlc(row, columns)
            if reason == "VALID":
                totals["valid_rows"] += 1
                g["valid_OHLC_rows"] += 1
                if is_listed_in_month:
                    try:
                        adj = float(row.get(columns["adjusted"]) or "")
                        if math.isfinite(adj) and adj > 0:
                            g["matched_month_valid_OHLC_adj_rows"] += 1
                            totals["matched_month_valid_OHLC_adj_rows"] += 1
                    except (ValueError, TypeError):
                        pass
            else:
                totals["invalid_rows"] += 1
                g["strict_invalid_OHLC_rows"] += 1

    old = phase21["source_counts"]
    expected = {"all_rows":old["all_source_rows"],
                "window_rows":old["window_rows"],
                "valid_rows":old["window_valid_ohlc_rows"],
                "invalid_rows":old["window_invalid_ohlc_rows"]}
    if any(totals[k] != v for k,v in expected.items()):
        raise PriceInputBlocked("PHASE21_PRICE_COUNTS_DO_NOT_RECONCILE")
    if len(overlap_ticker_strings) != old["period_unique_tickers_also_in_21_month_PIT"]:
        raise PriceInputBlocked("PHASE21_PIT_TICKER_COUNT_MISMATCH")

    records = []
    classes = Counter()
    for sid, g in sorted(groups.items()):
        listings = {}
        for ticker in sorted(g["ticker_strings"]):
            for (code,exchange), info in by_listing.items():
                if ticker != code:
                    continue
                listings[(code,exchange)] = info
        candidates = {}
        for info in listings.values():
            for match in info.get("candidate_sample_not_certified", []):
                local = local_id.get(str(match["security_id"]))
                if local is not None:
                    candidates[local["security_id"]] = local
        ciks = sorted({v["CIK_candidate"] for v in candidates.values()
                       if v["CIK_candidate"]})
        categories = sorted({d["category"] for d in listings.values()})
        multi_tickers = len(g["ticker_strings"]) > 1
        reused_tickers = any(len(ticker_to_ids[t]) > 1 for t in g["ticker_strings"])
        if multi_tickers:
            label = "SIMFIN_ID_MULTIPLE_TICKERS_REVIEW"
        elif reused_tickers:
            label = "TICKER_MULTIPLE_SIMFIN_IDS_REVIEW"
        elif len(ciks) > 1 or g["months_multiple_list_exchanges"]:
            label = "MULTIPLE_CIK_OR_EXCHANGE_CANDIDATES_REVIEW"
        elif len(ciks) == 1 and any(cat in DIRECT_TYPES for cat in categories):
            label = "ONE_PRESENT_DAY_SEC_CIK_CANDIDATE_NOT_HISTORICAL_PROOF"
        elif len(ciks) == 1:
            label = "ONE_WEAK_PRESENT_DAY_CIK_CANDIDATE_REVIEW"
        else:
            label = "NO_SEC_CIK_CANDIDATE"
        classes[label] += 1
        records.append({
            "SimFinId":sid,"ticker_strings":sorted(g["ticker_strings"]),
            "first_price_date":g["first_date"],"last_price_date":g["last_date"],
            "window_price_rows":g["window_rows"],
            "strict_valid_OHLC_rows":g["valid_OHLC_rows"],
            "strict_invalid_OHLC_rows":g["strict_invalid_OHLC_rows"],
            "calendar_months_price":len(g["months_with_price"]),
            "calendar_months_month_end_ticker_overlap":len(g["overlapping_months"]),
            "valid_OHLC_positive_adj_close_rows_with_month_end_ticker_overlap":
                g["matched_month_valid_OHLC_adj_rows"],
            "multiple_exchange_listed_calendar_months":
                sorted(g["months_multiple_list_exchanges"]),
            "phase20_identity_categories":categories,
            "candidate_CIKs_NOT_verified":ciks[:15],
            "local_security_id_candidates_NOT_verified":
                sorted(candidates)[:15],
            "review_class":label,
            "certified_historical_SimFinId_CIK":False,
        })
    return {
        "schema":SCHEMA,
        "status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
        "period":phase21["period"],
        "source_sha256":original_sha,
        "reconciled_phase19_20_21_23":True,
        "phase20_listing_keys":len(by_listing),
        "phase21_window_ticker_overlap":len(overlap_ticker_strings),
        "simfin_ids_in_window":len(groups),
        "ticker_strings_with_multiple_simfin_ids":
            sum(len(ids)>1 for ids in ticker_to_ids.values()),
        "simfin_ids_with_multiple_ticker_strings":
            sum(len(v)>1 for v in simfin_to_tickers.values()),
        "source_rows_without_simfin_id":totals["window_rows_missing_simfin_id"],
        "matched_month_valid_OHLC_positive_adj_close_rows_with_simfin_id":
            totals["matched_month_valid_OHLC_adj_rows"],
        "review_classes":dict(sorted(classes.items())),
        "candidate_records":records,
        "historical_identity_certifications":0,
        "historical_SimFinId_CIK_crosswalk_written_to_production":False,
        "ticker_only_identity_link_accepted":False,
        "delisting_returns_certified":False,
        "canonical_price_selections_written":0,
        "original_SEC_or_price_data_modified":False,
        "model_training_performed":False,
        "network_calls":0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    default = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--pit-dir", type=Path, default=default/"phase19/pit_staging")
    p.add_argument("--db", type=Path, default=default/"data/runtime/operational.db")
    p.add_argument("--phase20", type=Path,
                   default=default/"phase19/pit_identity_candidates.json")
    p.add_argument("--phase21", type=Path,
                   default=default/"phase21/simfin_free_price_source_audit.json")
    p.add_argument("--phase23", type=Path,
                   default=default/"phase23/simfin_nonpositive_ohlc_diagnostics.json")
    p.add_argument("--out", type=Path, default=default/"phase24/simfin_sec_cik_candidates.json")
    a = p.parse_args()
    try:
        result = analyze(a.input, a.pit_dir, a.db,a.phase20,a.phase21,a.phase23)
        dest = a.out.expanduser().resolve()
        dest.parent.mkdir(parents=True,exist_ok=True)
        temp=dest.with_suffix(".json.tmp")
        temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",
                        encoding="utf-8")
        temp.replace(dest)
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,zipfile.BadZipFile):
        print("PHASE24_BLOCKED: HISTORICAL_IDENTITY_CANDIDATE_SOURCE_INVALID")
        return 2
    print(json.dumps({
        "status":result["status"],"reconciled":result["reconciled_phase19_20_21_23"],
        "simfin_ids":result["simfin_ids_in_window"],
        "ticker_strings_with_multiple_simfin_ids":
            result["ticker_strings_with_multiple_simfin_ids"],
        "simfin_ids_with_multiple_ticker_strings":
            result["simfin_ids_with_multiple_ticker_strings"],
        "review_classes":result["review_classes"],
        "historical_identity_certifications":0,
        "canonical_price_selections_written":0,
        "report_file":str(dest),
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

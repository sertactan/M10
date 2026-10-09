"""Phase24b: audit local historical SEC evidence for Phase24 SimFinId/CIK candidates.

Research-only, SQLITE mode=ro, no network. This DOES NOT prove an SEC CIK
historically identifies a particular SimFin share class; historical price
selection, PIT, corporate actions and model training all stay blocked.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3

SCHEMA = "MERIDYEN_PHASE24B_SEC_CIK_EVIDENCE_GAP_AUDIT_V1"
SOURCE_SCHEMA = "MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1"
MAX_FILINGS_PER_ID = 500
MAX_ALIASES_PER_ID = 100
BATCH_SIZE = 300


def _cik(value):
    value = str(value or "").strip()
    return value.zfill(10) if value.isascii() and value.isdigit() and 0 < len(value) <= 10 and int(value) > 0 else None


def _has_tz(text):
    if not text:
        return False
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        return dt.tzinfo is not None and dt.utcoffset() is not None
    except (ValueError, TypeError):
        return False


def _groups(values, n=BATCH_SIZE):
    for idx in range(0, len(values), n):
        yield values[idx:idx+n]


def _read_index(con, ids, table, fields, limit_per_id):
    """Bounded indexed lookups; the limit is a real evidence caveat."""
    result = {}
    if not ids:
        return result
    for sid in ids:
        if table == "filing_records_source":
            sql = ("""SELECT cik,filing_date,accepted_at,accession_number
                        FROM filing_records_source
                        WHERE security_id=? AND source='SEC_EDGAR'
                        AND filing_date BETWEEN '2024-01-01' AND '2025-09-30'
                        LIMIT ?""")
        else:
            sql = ("""SELECT alias,valid_from,valid_to,source,availability_date
                        FROM ticker_aliases WHERE security_id=? LIMIT ?""")
        rows = con.execute(sql, (sid, limit_per_id + 1)).fetchall()
        result[sid] = {"rows": rows[:limit_per_id],
                       "truncated": len(rows) > limit_per_id}
    return result


def analyze(report_file: Path, db_file: Path, *, max_security_ids: int = 10000) -> dict:
    if report_file.is_symlink() or not report_file.is_file():
        raise ValueError("PHASE24_REPORT_MISSING")
    if db_file.is_symlink() or not db_file.is_file():
        raise ValueError("OPERATIONAL_DB_MISSING")
    raw = report_file.read_bytes()
    prev = json.loads(raw)
    if (prev.get("schema") != SOURCE_SCHEMA or
        prev.get("status") != "SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS"
        or prev.get("reconciled_phase19_20_21_23") is not True
        or prev.get("historical_identity_certifications") != 0):
        raise ValueError("PHASE24_REPORT_NOT_VERIFIED")
    records = prev.get("candidate_records")
    if (not isinstance(records, list) or
            len(records) != prev.get("simfin_ids_in_window") or
            len({str(r["SimFinId"]) for r in records}) != len(records)):
        raise ValueError("PHASE24_RECORD_COUNT_INVALID")
    ids = sorted({str(sid) for r in records for sid in
                  r.get("local_security_id_candidates_NOT_verified", [])})
    if len(ids) > max_security_ids:
        raise ValueError("TOO_MANY_CANDIDATE_SECURITY_IDS")
    con = sqlite3.connect(db_file.resolve().as_uri() + "?mode=ro",
                          uri=True, timeout=5)
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=5000")
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "security_master" not in tables:
            raise ValueError("SECURITY_MASTER_MISSING")
        required = {"security_id", "cik", "ticker", "exchange"}
        cols = {r[1] for r in con.execute("PRAGMA table_info(security_master)")}
        if not required.issubset(cols):
            raise ValueError("SECURITY_MASTER_COLUMNS_MISSING")
        optional_figi = "share_class_figi" in cols
        optional_composite = "composite_figi" in cols
        figi_clause = (",share_class_figi" if optional_figi else "") + (
            ",composite_figi" if optional_composite else "")
        master = {}
        for batch in _groups(ids):
            qs = ",".join("?" for _ in batch)
            for row in con.execute(
                f"SELECT security_id,cik,ticker,exchange{figi_clause} "
                f"FROM security_master WHERE security_id IN ({qs})", batch
            ):
                sid, cik, ticker, exchange, *extra = row
                master[str(sid)] = {
                    "cik": _cik(cik),
                    "ticker": str(ticker or "").strip().upper(),
                    "exchange": str(exchange or "").strip().upper(),
                    "figi_in_current_master": (
                        bool(extra[0]) if optional_figi else False),
                    "composite_figi_in_current_master": (
                        bool(extra[1 if optional_figi else 0])
                        if optional_composite else False),
                }
        filings_available = "filing_records_source" in tables
        aliases_available = "ticker_aliases" in tables
        if filings_available:
            fc = {r[1] for r in con.execute(
                "PRAGMA table_info(filing_records_source)")}
            filings_available = {"security_id","source","cik","filing_date",
                                 "accepted_at","accession_number"}.issubset(fc)
        if aliases_available:
            ac = {r[1] for r in con.execute(
                "PRAGMA table_info(ticker_aliases)")}
            aliases_available = {"security_id","alias","valid_from","valid_to",
                                 "source","availability_date"}.issubset(ac)
        filings = (_read_index(con, ids, "filing_records_source", None,
                               MAX_FILINGS_PER_ID) if filings_available else {})
        aliases = (_read_index(con, ids, "ticker_aliases", None,
                               MAX_ALIASES_PER_ID) if aliases_available else {})
    finally:
        con.close()

    categories = Counter()
    items = []
    for record in records:
        first = date.fromisoformat(record["first_price_date"])
        last = date.fromisoformat(record["last_price_date"])
        ticker_set = {str(t).upper() for t in record.get("ticker_strings", [])}
        candidate_ids = [str(v) for v in
                         record.get("local_security_id_candidates_NOT_verified", [])]
        original_ciks = {_cik(v) for v in record.get("candidate_CIKs_NOT_verified", [])}
        original_ciks.discard(None)
        current_ciks = {master[sid]["cik"] for sid in candidate_ids if
                        sid in master and master[sid]["cik"]}
        master_unchanged = original_ciks == current_ciks
        eligible_filings = 0
        missing_timestamps = 0
        filing_conflicts = 0
        bounded_dated_aliases = 0
        truncated = False
        current_figi = False
        for sid in candidate_ids:
            local = master.get(sid)
            if not local:
                continue
            current_figi |= local["figi_in_current_master"]
            f = filings.get(sid, {})
            truncated |= bool(f.get("truncated"))
            for cik, filing_date, accepted, accession in f.get("rows", []):
                try:
                    filed = date.fromisoformat(str(filing_date))
                except (TypeError, ValueError):
                    filing_conflicts += 1
                    continue
                if not first <= filed <= last:
                    continue
                if _cik(cik) != local["cik"] or not accession:
                    filing_conflicts += 1
                elif _has_tz(accepted):
                    eligible_filings += 1
                else:
                    missing_timestamps += 1
            a = aliases.get(sid, {})
            truncated |= bool(a.get("truncated"))
            for alias, valid_from, valid_to, source, availability_date in a.get("rows", []):
                if not (alias and str(alias).upper() in ticker_set and
                        valid_from and valid_to and source and
                        str(source).upper() not in ("UNKNOWN","") and availability_date):
                    continue
                try:
                    start_alias = date.fromisoformat(str(valid_from))
                    end_alias = date.fromisoformat(str(valid_to))
                    available = date.fromisoformat(str(availability_date)[:10])
                    if start_alias <= last and first <= end_alias and available <= last:
                        bounded_dated_aliases += 1
                except (TypeError, ValueError):
                    pass
        conflict = (
            record.get("review_class") in
            {"MULTIPLE_CIK_OR_EXCHANGE_CANDIDATES_REVIEW",
             "SIMFIN_ID_MULTIPLE_TICKERS_REVIEW",
             "TICKER_MULTIPLE_SIMFIN_IDS_REVIEW"}
            or len(current_ciks) > 1 or len(original_ciks) > 1
            or not master_unchanged or filing_conflicts > 0
        )
        if conflict:
            label = "CONFLICT_OR_CHANGED_LOCAL_CIK_REQUIRES_REVIEW"
        elif not current_ciks:
            label = "NO_SEC_CIK_CANDIDATE"
        elif eligible_filings and bounded_dated_aliases:
            label = "SEC_ACCEPTANCE_AND_DATED_ALIAS_CANDIDATES_REVIEW"
        elif eligible_filings:
            label = "SEC_ACCEPTANCE_EVIDENCE_ONLY_REVIEW"
        elif bounded_dated_aliases:
            label = "DATED_ALIAS_ONLY_REVIEW"
        else:
            label = "CURRENT_MASTER_CIK_ONLY_NOT_HISTORICAL"
        categories[label] += 1
        items.append({
            "SimFinId": record["SimFinId"],
            "ticker_strings": sorted(ticker_set),
            "CIK_candidates_NOT_historically_certified": sorted(current_ciks),
            "historical_sec_filing_with_timestamp_candidate_count": eligible_filings,
            "filing_without_timezone_or_missing_timestamp_count": missing_timestamps,
            "filing_CIK_accession_conflicts": filing_conflicts,
            "dated_ticker_alias_candidate_count": bounded_dated_aliases,
            "current_share_class_figi_present_NOT_historic": current_figi,
            "evidence_lookup_truncated": truncated,
            "classification": label,
            "historical_security_identity_certified": False,
        })
    return {
        "schema": SCHEMA, "status": "SEC_FILING_AND_ALIAS_EVIDENCE_GAPS_MEASURED_NOT_CERTIFIED",
        "phase24_report_sha256": hashlib.sha256(raw).hexdigest(),
        "simfin_ids_reviewed": len(records),
        "current_security_master_ids_checked": len(ids),
        "filing_records_schema_available": filings_available,
        "dated_ticker_alias_schema_available": aliases_available,
        "review_classes": dict(sorted(categories.items())),
        "potential_evidence_lookup_truncated_ids": sum(
            x.get("truncated",False) for x in
            list(filings.values()) + list(aliases.values())),
        "records": items,
        "historic_SimFinId_CIK_certifications": 0,
        "original_SEC_submissions_provenance_verified": False,
        "price_split_dividend_delisting_verified": False,
        "operational_database_modified": False,
        "canonical_price_selections_written": 0,
        "model_training_performed": False,
        "paid_API_requests": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    root = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime"
    )
    p.add_argument("--phase24", type=Path,
                   default=root/"phase24/simfin_sec_cik_candidates.json")
    p.add_argument("--db", type=Path,
                   default=root/"data/runtime/operational.db")
    p.add_argument("--out", type=Path,
                   default=root/"phase24b/sec_identity_evidence_gaps.json")
    a = p.parse_args()
    try:
        result = analyze(a.phase24, a.db)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        part = a.out.with_suffix(".json.tmp")
        part.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",
                        encoding="utf-8")
        part.replace(a.out)
    except (ValueError,TypeError,KeyError,sqlite3.Error,OSError):
        print("PHASE24B_BLOCKED: PRIOR_REPORT_OR_SQLITE_EVIDENCE_INVALID")
        return 2
    print(json.dumps({
        "status": result["status"],
        "simfin_ids_reviewed": result["simfin_ids_reviewed"],
        "security_ids_checked": result["current_security_master_ids_checked"],
        "filings_table_available": result["filing_records_schema_available"],
        "aliases_table_available": result["dated_ticker_alias_schema_available"],
        "review_classes": result["review_classes"],
        "evidence_lookup_truncated_ids":
            result["potential_evidence_lookup_truncated_ids"],
        "historical_certifications": 0,
        "report_file": str(a.out),
        "database_modified": False,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

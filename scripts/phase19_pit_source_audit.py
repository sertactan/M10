"""Read-only 21-month Alpha Vantage listing-source audit; NEVER certify PIT identity.

Checks local CSV/manifest SHA-256, counts distinct ticker+exchange *listing
keys*, and optionally audits tentative links to installed SEC security_master.
No API calls, production DB writes, or canonical model side effects.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3

from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider
from scripts.phase19_alpha_pit_staging import month_ends


SOURCE = "ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY"
REPORT_SCHEMA = "MERIDYEN_PHASE19_PIT_SOURCE_AUDIT_V1"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _db_identity_audit(db: Path, listing_keys: set[tuple[str, str]]) -> dict:
    result = {
        "status": "NOT_CHECKED", "db_file_exists": db.is_file(),
        "matched_single_db_security_id_with_cik": 0,
        "matched_single_db_security_id_without_cik": 0,
        "multiple_db_security_ids_same_listing_key": 0,
        "no_current_db_match": 0,
        "sample_ambiguous_keys": [], "sample_missing_keys": [],
        "historical_cik_figi_mapping_certified": False,
    }
    if not db.is_file() or db.is_symlink():
        result["status"] = "BLOCKED_DB_MISSING_OR_SYMLINK"
        return result
    try:
        # URI mode=ro prevents SQLite from silently creating a second DB.
        con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=15)
        try:
            con.execute("PRAGMA query_only=ON")
            table = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='security_master'"
            ).fetchone()
            if table is None:
                result["status"] = "BLOCKED_SECURITY_MASTER_MISSING"
                return result
            matches: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
            rows = con.execute(
                """SELECT ticker,exchange,security_id,cik FROM security_master
                   WHERE market='US' AND exchange IN ('NASDAQ','NYSE','AMEX')"""
            )
            for ticker, exchange, sid, cik in rows:
                key = (str(ticker).upper().strip(), str(exchange).upper().strip())
                if key in listing_keys:
                    matches[key].append((str(sid), str(cik or "").strip()))
            for key in sorted(listing_keys):
                entries = matches.get(key, [])
                if not entries:
                    result["no_current_db_match"] += 1
                    if len(result["sample_missing_keys"]) < 15:
                        result["sample_missing_keys"].append(list(key))
                elif len({sid for sid, _ in entries}) > 1:
                    result["multiple_db_security_ids_same_listing_key"] += 1
                    if len(result["sample_ambiguous_keys"]) < 15:
                        result["sample_ambiguous_keys"].append(list(key))
                elif any(cik for _, cik in entries):
                    result["matched_single_db_security_id_with_cik"] += 1
                else:
                    result["matched_single_db_security_id_without_cik"] += 1
            result["status"] = "CURRENT_DB_CANDIDATES_ONLY_NOT_HISTORICAL_IDENTITY"
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        result["status"] = "BLOCKED_READ_ONLY_DB_ERROR"
    return result


def audit(root: Path, *, start: date, end: date, db: Path | None = None) -> dict:
    dates = month_ends(start, end)
    if not dates:
        raise ValueError("NO_MONTH_ENDS")
    if root.is_symlink():
        raise ValueError("SOURCE_DIRECTORY_SYMLINK")
    findings: list[str] = []
    months: list[dict] = []
    by_month: list[set[tuple[str, str]]] = []
    keyed_names: dict[tuple[str, str], set[str]] = defaultdict(set)
    same_symbol_exchanges: dict[str, set[str]] = defaultdict(set)
    duplicate_samples: list[dict] = []
    duplicates_by_month: list[dict] = []
    for as_of in dates:
        stamp = as_of.isoformat()
        csv_path = root / (stamp + ".csv")
        manifest_path = root / (stamp + ".manifest.json")
        if csv_path.is_symlink() or manifest_path.is_symlink():
            findings.append("SYMLINK_SOURCE_FILE:" + stamp)
            continue
        if not csv_path.is_file() or not manifest_path.is_file():
            findings.append("MISSING_CSV_OR_MANIFEST:" + stamp)
            continue
        try:
            payload = csv_path.read_bytes()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("INVALID_MANIFEST_OBJECT")
            if (manifest.get("as_of") != stamp or
                manifest.get("source") != SOURCE or
                manifest.get("sha256") != _digest(payload) or
                manifest.get("bytes") != len(payload)):
                raise ValueError("SOURCE_HASH_OR_METADATA_MISMATCH")
            records = AlphaVantagePitUniverseProvider.parse_csv(
                payload.decode("utf-8-sig"), as_of=as_of
            )
            counts = {market: sum(1 for item in records if item.exchange.value == market)
                      for market in ("NASDAQ", "NYSE", "AMEX")}
            if (len(records) != manifest.get("qualified_stock_rows") or
                counts != manifest.get("exchange_counts") or
                sum(counts.values()) != len(records)):
                raise ValueError("SOURCE_ROW_COUNT_MISMATCH")
            keys = [(item.ticker.upper(), item.exchange.value) for item in records]
            frequency = Counter(keys)
            dupes = {key: count for key, count in frequency.items() if count > 1}
            # Duplicate raw rows do not invalidate a source whose exact bytes,
            # manifest and totals verified. But historical security identity
            # must remain blocked; a duplicated ticker must NEVER be silently
            # interpreted as one issuer.
            duplicate_rows = sum(n - 1 for n in dupes.values())
            duplicates_by_month.append({
                "as_of": stamp, "duplicate_key_groups": len(dupes),
                "extra_rows_with_repeated_listing_key": duplicate_rows,
            })
            for key, count in sorted(dupes.items()):
                if len(duplicate_samples) >= 30:
                    break
                duplicate_samples.append({
                    "as_of": stamp, "ticker": key[0], "exchange": key[1],
                    "raw_rows_with_key": count,
                })
            by_month.append(set(keys))
            for record in records:
                key = (record.ticker.upper(), record.exchange.value)
                keyed_names[key].add(record.name.casefold().strip())
                same_symbol_exchanges[record.ticker.upper()].add(record.exchange.value)
            months.append({"as_of": stamp, "qualified_stock_rows": len(records),
                           "distinct_listing_keys": len(set(keys)),
                           "duplicate_listing_key_groups": len(dupes),
                           "extra_rows_with_repeated_listing_key": duplicate_rows,
                           "exchange_counts": counts,
                           "sha256": manifest["sha256"]})
        except (UnicodeError, ValueError, KeyError, TypeError, OSError) as exc:
            # Only disclose allowlisted machine-readable codes; never source
            # payload, private filesystem paths, request URLs or API secrets.
            cause = str(exc)
            safe_code = (cause if re.fullmatch(r"[A-Z0-9_]{3,80}", cause)
                         else type(exc).__name__.upper())
            findings.append("INVALID_SOURCE_" + stamp + "_" + safe_code)
    unique_keys = set().union(*by_month) if by_month else set()
    changes = []
    for before, after, month in zip(by_month, by_month[1:], months[1:]):
        changes.append({"as_of": month["as_of"],
                        "new_listing_keys_since_previous_month": len(after - before),
                        "absent_listing_keys_since_previous_month": len(before - after)})
    all_files_verified = not findings and len(months) == len(dates)
    duplicate_groups = sum(m["duplicate_key_groups"] for m in duplicates_by_month)
    source_status = (
        "BLOCKED_SOURCE_ARCHIVE_INCOMPLETE_OR_INVALID" if not all_files_verified
        else ("SOURCE_ARCHIVE_VERIFIED_WITH_IDENTITY_WARNINGS_NOT_PIT_CERTIFIED"
              if duplicate_groups else "SOURCE_ARCHIVE_VERIFIED_NOT_PIT_CERTIFIED")
    )
    result = {
        "schema": REPORT_SCHEMA,
        "status": source_status,
        "start": start.isoformat(), "end": end.isoformat(),
        "requested_months": len(dates), "verified_months": len(months),
        "monthly_source_records": months,
        "duplicate_listing_key_groups_across_months": duplicate_groups,
        "extra_raw_rows_with_repeated_listing_keys_across_months": sum(
            m["extra_rows_with_repeated_listing_key"] for m in duplicates_by_month),
        "monthly_duplicate_listing_keys": duplicates_by_month,
        "sample_duplicate_listing_keys": duplicate_samples,
        "distinct_ticker_exchange_listing_keys": len(unique_keys),
        "distinct_ticker_strings": len({k[0] for k in unique_keys}),
        "listing_key_with_name_variations": len(
            [1 for names in keyed_names.values() if len(names) > 1]),
        "ticker_appearing_on_multiple_exchanges": len(
            [1 for v in same_symbol_exchanges.values() if len(v) > 1]),
        "monthly_key_changes_not_delisting_proof": changes,
        "examples_name_variations": [
            {"ticker": k[0], "exchange": k[1], "name_count": len(names)}
            for k, names in sorted(keyed_names.items()) if len(names) > 1
        ][:15],
        "findings": findings[:40],
        "current_security_master_candidate_match": (
            _db_identity_audit(db, unique_keys) if db is not None else
            {"status": "NOT_REQUESTED", "historical_cik_figi_mapping_certified": False}),
        "original_pit_identity_certified": False,
        "delisting_payoffs_certified": False,
        "adjusted_prices_certified": False,
        "canonical_model_readiness": "BLOCKED_HISTORICAL_IDENTITY_AND_ADJUSTED_PRICES",
        "production_database_modified": False,
        "model_training_performed": False,
    }
    # Do not confuse a listing key or historic CSV count with unique issuers.
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2025-09-30")
    default_root = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime/phase19/pit_staging"
    )
    p.add_argument("--staging-dir", type=Path, default=default_root)
    p.add_argument("--db", type=Path, default=None,
                   help="Optional installed operational.db, queried in SQLite read-only mode")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    root = args.staging_dir.expanduser().resolve()
    report = audit(root, start=date.fromisoformat(args.start),
                   end=date.fromisoformat(args.end), db=args.db)
    # Report lives beside source files by default, NOT in the SEC or M10 DB.
    out = args.out or (root / "phase19_listing_source_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "verified_months": report["verified_months"],
        "requested_months": report["requested_months"],
        "distinct_ticker_exchange_listing_keys":
            report["distinct_ticker_exchange_listing_keys"],
        "distinct_ticker_strings": report["distinct_ticker_strings"],
        "listing_key_with_name_variations": report["listing_key_with_name_variations"],
        "duplicate_listing_key_groups_across_months":
            report["duplicate_listing_key_groups_across_months"],
        "extra_raw_rows_with_repeated_listing_keys_across_months":
            report["extra_raw_rows_with_repeated_listing_keys_across_months"],
        "sample_duplicate_listing_keys": report["sample_duplicate_listing_keys"][:10],
        "ticker_appearing_on_multiple_exchanges":
            report["ticker_appearing_on_multiple_exchanges"],
        "current_security_master_candidate_match":
            report["current_security_master_candidate_match"],
        "findings": report["findings"],
        "full_report": str(out),
        "original_pit_identity_certified": False,
        "production_database_modified": False,
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] in (
        "SOURCE_ARCHIVE_VERIFIED_NOT_PIT_CERTIFIED",
        "SOURCE_ARCHIVE_VERIFIED_WITH_IDENTITY_WARNINGS_NOT_PIT_CERTIFIED",
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())

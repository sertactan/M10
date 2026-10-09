"""Phase 20: offline candidate triage of historic US listings against local M10 IDs.

Reads existing Alpha Vantage CSV+SHA manifests and operational.db in SQLite
mode=ro. NEVER inserts CIK, maps ticker reuse automatically, or certifies
historical issuer/security identities. No provider/network calls.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
import os
from pathlib import Path
import re
import sqlite3

from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider
from scripts.phase19_alpha_pit_staging import month_ends
from scripts.phase19_pit_source_audit import audit


SCHEMA = "MERIDYEN_PHASE20_HISTORICAL_IDENTITY_CANDIDATES_V1"
AUDIT_OK = {
    "SOURCE_ARCHIVE_VERIFIED_NOT_PIT_CERTIFIED",
    "SOURCE_ARCHIVE_VERIFIED_WITH_IDENTITY_WARNINGS_NOT_PIT_CERTIFIED",
}


def _name_key(value: str) -> str:
    # Strictly a proposed lookup; no suffix-stripping or fuzzy scoring.
    return re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()


def _read_db(db: Path) -> tuple[dict, dict, dict, bool, dict]:
    if db.is_symlink() or not db.is_file():
        raise ValueError("INSTALLED_DB_NOT_FOUND_OR_SYMLINK")
    connection = sqlite3.connect(db.resolve().as_uri() + "?mode=ro",
                                 uri=True, timeout=15)
    try:
        connection.execute("PRAGMA query_only=ON")
        columns = {r[1] for r in connection.execute("PRAGMA table_info(security_master)")}
        if not {"ticker", "exchange", "name", "security_id", "cik", "market"}.issubset(columns):
            raise ValueError("SECURITY_MASTER_SCHEMA_INCOMPLETE")
        by_ticker_exchange: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
        by_ticker: dict[str, dict[str, dict]] = defaultdict(dict)
        by_name: dict[str, dict[str, dict]] = defaultdict(dict)
        for sid, ticker, name, exchange, cik in connection.execute(
            "SELECT security_id,ticker,name,exchange,cik FROM security_master WHERE market='US'"
        ):
            item = {"security_id": str(sid), "cik_present": bool(str(cik or "").strip()),
                    "current_exchange": str(exchange).upper().strip()}
            tick = str(ticker or "").upper().strip()
            key = (tick, item["current_exchange"])
            by_ticker_exchange[key][item["security_id"]] = item
            by_ticker[tick][item["security_id"]] = item
            norm = _name_key(str(name or ""))
            if norm:
                by_name[norm][item["security_id"]] = item
        aliases: dict[str, dict[str, dict]] = defaultdict(dict)
        aliases_available = bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ticker_aliases'"
        ).fetchone())
        if aliases_available:
            cols = {r[1] for r in connection.execute("PRAGMA table_info(ticker_aliases)")}
            if not {"alias", "security_id"}.issubset(cols):
                raise ValueError("TICKER_ALIASES_SCHEMA_INCOMPLETE")
            # Aliases only matter when their security_id exists in security_master.
            all_sids = {sid: v for by_key in by_ticker_exchange.values()
                        for sid, v in by_key.items()}
            for alias, sid in connection.execute("SELECT alias,security_id FROM ticker_aliases"):
                item = all_sids.get(str(sid))
                if item:
                    aliases[str(alias or "").upper().strip()][str(sid)] = item
        return by_ticker_exchange, by_ticker, by_name, aliases_available, aliases
    finally:
        connection.close()


def _small_candidates(items: dict[str, dict], maximum=6) -> list[dict]:
    # Candidate IDs are LOCAL research IDs, not certified identity linkages.
    return [
        {"security_id": item["security_id"], "cik_present": item["cik_present"],
         "db_current_exchange": item["current_exchange"]}
        for _, item in sorted(items.items())[:maximum]
    ]


def classify(key: tuple[str, str], names: set[str], direct: dict,
             by_ticker: dict, by_name: dict, aliases: dict) -> tuple[str, list[dict], dict]:
    ticker, exchange = key
    exact = direct.get(key, {})
    evidence = {
        "same_ticker_different_exchange": False,
        "ticker_alias_candidate": False,
        "exact_normalized_name_candidate": False,
        "ambiguous_candidate_count": 0,
    }
    if len(exact) > 1:
        return "AMBIGUOUS_CURRENT_DB_MATCH", _small_candidates(exact), evidence
    if exact:
        item = next(iter(exact.values()))
        return ("CURRENT_TICKER_EXCHANGE_CIK_CANDIDATE" if item["cik_present"]
                else "CURRENT_TICKER_EXCHANGE_NO_CIK"), _small_candidates(exact), evidence

    other_exchanges = {
        sid: v for sid, v in by_ticker.get(ticker, {}).items()
        if v["current_exchange"] != exchange
    }
    alias_candidates = aliases.get(ticker, {})
    name_candidates: dict[str, dict] = {}
    for name in names:
        norm = _name_key(name)
        if norm:
            name_candidates.update(by_name.get(norm, {}))
    evidence["same_ticker_different_exchange"] = bool(other_exchanges)
    evidence["ticker_alias_candidate"] = bool(alias_candidates)
    evidence["exact_normalized_name_candidate"] = bool(name_candidates)
    union = dict(other_exchanges)
    union.update(alias_candidates)
    union.update(name_candidates)
    evidence["ambiguous_candidate_count"] = len(union) if len(union) > 1 else 0
    if len(union) > 1:
        return "MULTIPLE_WEAK_CANDIDATES_REVIEW_ONLY", _small_candidates(union), evidence
    if other_exchanges:
        return "OTHER_EXCHANGE_TICKER_CANDIDATE", _small_candidates(union), evidence
    if alias_candidates:
        return "ALIAS_TICKER_CANDIDATE", _small_candidates(union), evidence
    if name_candidates:
        return "NORMALIZED_NAME_CANDIDATE", _small_candidates(union), evidence
    return "NO_LOCAL_IDENTITY_CANDIDATE", [], evidence


def run(root: Path, db: Path, start: date, end: date) -> dict:
    verified = audit(root, start=start, end=end)  # hashes and rows verified first
    if verified["status"] not in AUDIT_OK:
        raise ValueError("PIT_SOURCE_AUDIT_NOT_VERIFIED")
    direct, by_ticker, by_name, aliases_available, aliases = _read_db(db)
    listing: dict[tuple[str, str], dict] = {}
    for stamp in month_ends(start, end):
        records = AlphaVantagePitUniverseProvider.parse_csv(
            (root / (stamp.isoformat() + ".csv")).read_text(encoding="utf-8-sig"),
            as_of=stamp,
        )
        per_month = Counter((r.ticker.upper(), r.exchange.value) for r in records)
        for item in records:
            key = (item.ticker.upper(), item.exchange.value)
            if key not in listing:
                listing[key] = {"months": set(), "names": set(), "duplicate_extra_rows": 0}
            listing[key]["months"].add(stamp.isoformat())
            listing[key]["names"].add(item.name)
        for key, count in per_month.items():
            listing[key]["duplicate_extra_rows"] += max(0, count - 1)
    categories = Counter()
    details = []
    for key, meta in sorted(listing.items()):
        category, candidates, flags = classify(
            key, meta["names"], direct, by_ticker, by_name, aliases
        )
        categories[category] += 1
        months = sorted(meta["months"])
        details.append({
            "ticker": key[0], "exchange": key[1], "category": category,
            "first_month_seen": months[0], "last_month_seen": months[-1],
            "months_seen": len(months), "name_variation_count": len(meta["names"]),
            "source_name_examples": sorted(meta["names"])[:3],
            "extra_duplicate_rows": meta["duplicate_extra_rows"],
            "candidate_count_displayed": len(candidates),
            "candidate_sample_not_certified": candidates,
            "weak_evidence_flags": flags,
        })
    total = len(listing)
    if total != verified["distinct_ticker_exchange_listing_keys"]:
        raise ValueError("RECONCILIATION_KEY_COUNT_MISMATCH")
    return {
        "schema": SCHEMA,
        "status": "CANDIDATES_ONLY_HISTORICAL_IDENTITY_NOT_CERTIFIED",
        "months_verified": verified["verified_months"],
        "distinct_ticker_exchange_listing_keys": total,
        "categories": dict(sorted(categories.items())),
        "duplicates_across_months": verified["duplicate_listing_key_groups_across_months"],
        "aliases_table_available": aliases_available,
        "unresolved_or_weak_candidate_keys": sum(
            count for cat, count in categories.items()
            if cat not in ("CURRENT_TICKER_EXCHANGE_CIK_CANDIDATE",
                           "CURRENT_TICKER_EXCHANGE_NO_CIK")
        ),
        "details": details,
        "historical_cik_figi_mapping_certified": False,
        "canonicity": "RESEARCH_ONLY_NO_PRODUCTION_PIT_WRITE",
        "backtest_ready": False,
        "model_training_performed": False,
        "database_modified": False,
        "paid_api_used": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime"
    )
    p.add_argument("--staging-dir", type=Path,
                   default=base / "phase19/pit_staging")
    p.add_argument("--db", type=Path, default=base / "data/runtime/operational.db")
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2025-09-30")
    p.add_argument("--out", type=Path, default=base / "phase19/pit_identity_candidates.json")
    args = p.parse_args()
    try:
        report = run(args.staging_dir.expanduser().resolve(),
                     args.db.expanduser().resolve(),
                     date.fromisoformat(args.start), date.fromisoformat(args.end))
    except (ValueError, sqlite3.Error, OSError) as exc:
        # No raw SQL/paths/API secrets in errors.
        print("PHASE20_BLOCKED:", type(exc).__name__)
        return 2
    destination = args.out.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(destination)
    print(json.dumps({
        "status": report["status"],
        "months_verified": report["months_verified"],
        "distinct_ticker_exchange_listing_keys": report["distinct_ticker_exchange_listing_keys"],
        "categories": report["categories"],
        "duplicates_across_months": report["duplicates_across_months"],
        "unresolved_or_weak_candidate_keys": report["unresolved_or_weak_candidate_keys"],
        "report_file": str(destination),
        "database_modified": False,
        "historical_cik_figi_mapping_certified": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

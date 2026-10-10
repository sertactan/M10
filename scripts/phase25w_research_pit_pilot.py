"""Phase25W: private, read-only 2024-2025 research-cohort and PIT blocker audit.

Uses EXISTING Phase25Q staging and Phase25R QA, never imports/proclaims PIT.
Does not edit S15/S16, run WF9, calculate returns or touch source databases.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

SCHEMA = "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1"
WINDOW = {"start": "2024-01-01", "end": "2025-09-30"}
STRONG_CONFLICTS = ("B", "CWBC", "FUN", "STRR", "TEL", "TTE", "VIVO")
# Documented official-event research references; NOT a certified time-varying
# security-master, PIT-available feature or vendor corporate-action adjustment.
OFFICIAL_CASES = {
    "B": ("CASH_MERGER_AND_TICKER_REUSE", (
        "https://www.sec.gov/Archives/edgar/data/9984/000114036125001965/ef20042046_8k.htm",
        "https://www.barrick.com/English/news/news-details/2025/barrick-announces-name-change-to-barrick-mining-corporation-and-election-of-directors/default.aspx")),
    "CWBC": ("SHARE_EXCHANGE_AND_TICKER_REUSE", (
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2024-160",
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=dtn2024-8")),
    "FUN": ("MERGER_OLD_UNITS_AND_SUCCESSOR_STOCK", (
        "https://www.sec.gov/Archives/edgar/data/701374/000119312524173426/d813704dex991.htm",)),
    "STRR": ("TICKER_AND_ENTITY_TRANSITION", (
        "https://www.sec.gov/Archives/edgar/data/1210708/000121070825000081/pressreleaseofhudsonglobal.htm",)),
    "TEL": ("ONE_TO_ONE_REINCORPORATION", (
        "https://investors.te.com/news-releases/press-release-details/2024/TE-Connectivity-completes-change-in-place-of-incorporation-to-Ireland/default.aspx",)),
    "TTE": ("ADS_CLASS_AND_LATER_SHARE_CONVERSION", (
        "https://www.sec.gov/Archives/edgar/data/879764/000110465925029751/tot-20241231x20f.htm",)),
    "VIVO": ("OLD_SECURITY_CASH_ACQUISITION_2023", (
        "https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2023-49",)),
    "SITC": ("REVERSE_SPLIT_AND_CURB_SPINOFF", (
        "https://www.sec.gov/Archives/edgar/data/894315/000095017024099069/sitc-20240816.htm",
        "https://www.sec.gov/Archives/edgar/data/894315/000119312524231147/d104351dex991.htm")),
}

BLOCKERS = (
    "RETROSPECTIVE_2026_MONTH_END_FILES_NOT_2024_2025_CONTEMPORANEOUS_PIT",
    "DAILY_SECURITY_CIK_CLASS_IDENTITIES_NOT_CERTIFIED",
    "485_SOURCE_DUPLICATES_MUST_NOT_BE_TICKER_ONLY_JOINED",
    "CORPORATE_ACTION_DISTRIBUTION_AND_VENDOR_ADJUSTMENTS_NOT_CERTIFIED",
    "DELISTING_TERMINAL_RETURNS_NOT_CERTIFIED",
    "SEC_PUBLIC_DISSEMINATION_AND_VENDOR_AVAILABLE_AT_NOT_CERTIFIED",
    "FULL_UNIVERSE_SURVIVORSHIP_AND_CENSORING_NOT_RESOLVED",
)


def _json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("MISSING_OR_SYMLINK_SOURCE_REPORT")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("SOURCE_REPORT_NOT_OBJECT")
    return obj


def _ro(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("LOCAL_DATABASE_NOT_ACCESSIBLE")
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def _probe_market(path):
    try:
        with closing(_ro(path)) as con:
            tables = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            queries = {
                "historical_membership_rows": (
                    "universe_snapshot_membership",
                    "SELECT COUNT(*) FROM universe_snapshot_membership "
                    "WHERE snapshot_date BETWEEN ? AND ?",
                    (WINDOW["start"], WINDOW["end"])),
                "backtest_adjusted_selections": (
                    "canonical_price_selection",
                    "SELECT COUNT(*) FROM canonical_price_selection "
                    "WHERE purpose='BACKTEST_ADJUSTED' AND start_date<=? AND end_date>=?",
                    (WINDOW["end"], WINDOW["start"])),
                "corporate_action_rows": (
                    "corporate_actions", "SELECT COUNT(*) FROM corporate_actions", ()),
            }
            found = {}
            for key, (table, sql, args) in queries.items():
                found[key] = (int(con.execute(sql, args).fetchone()[0])
                              if table in tables else None)
            return {"status": "REAL_OPERATIONAL_DB_READ_ONLY", **found}
    except (ValueError, sqlite3.Error, OSError):
        return {"status": "OPERATIONAL_DB_NOT_ACCESSIBLE",
                "historical_membership_rows": None,
                "backtest_adjusted_selections": None,
                "corporate_action_rows": None}


def assess(manifest_path, qa_path, operational_db, *, pilot_size=25, sitc_path=None):
    if not 1 <= pilot_size <= 100:
        raise ValueError("PILOT_SIZE_MUST_BE_1_TO_100")
    m, q = _json(manifest_path), _json(qa_path)
    if (m.get("schema") != "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1"
        or m.get("status") != "RESEARCH_ONLY_NOT_CANONICAL_PIT"
        or m.get("period") != WINDOW or m.get("month_end_snapshots") != 21
        or m.get("month_end_retrieved_after_backtest_window") is not True
        or m.get("canonical_ready") is not False
        or m.get("backtest_eligible_securities") != 0
        or m.get("production_DB_modified") is not False
        or q.get("schema") != "MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1"
        or q.get("status") != "21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL"
        or q.get("staging_version") != m.get("staging_version")
        or q.get("canonical_approved_rows") != 0
        or q.get("distinct_monthly_ticker_exchange_keys") != m.get("monthly_membership_rows")
        or q.get("price_and_membership_counts", {}).get("source_price_rows") != m.get("source_daily_valid_price_rows")
    ):
        raise ValueError("PHASE25Q_25R_SOURCE_CONTRACT_OR_VERSION_MISMATCH")

    conflicts = q.get("membership_identity_conflict_quarantine")
    if (not isinstance(conflicts, list) or len(conflicts) != 464
        or q.get("conflicting_month_ticker_exchange_identity_rows") != 464
        or q.get("conflicting_distinct_ticker_strings") != 30
        or sorted(q.get("conflicting_strong_cohort_tickers", [])) != sorted(STRONG_CONFLICTS)
        or any(c.get("conflicting_company_identity_quarantined") is not True
               or not all(c.get(k) for k in ("month_end", "ticker", "exchange",
                                             "first_issuer_name", "second_issuer_name"))
               for c in conflicts)):
        raise ValueError("464_CONFLICTS_OR_STRONG_TICKER_QUARANTINE_NOT_RECONCILED")
    risk_tickers = {str(c["ticker"]) for c in conflicts}
    if len(risk_tickers) != 30:
        raise ValueError("CONFLICT_TICKER_SET_MISMATCH")

    stage_path = Path(m["staging_db"])
    with closing(_ro(stage_path)) as con:
        quick = con.execute("PRAGMA quick_check").fetchone()
        if not quick or quick[0] != "ok":
            raise ValueError("STAGING_SQLITE_QUICK_CHECK_FAILED")
        required = {"source_daily_price", "candidate_gate", "candidate_identity",
                    "monthly_research_membership"}
        present = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= present:
            raise ValueError("STAGING_REQUIRED_TABLES_MISSING")
        if con.execute("SELECT COUNT(*) FROM source_daily_price").fetchone()[0] != m["source_daily_valid_price_rows"]:
            raise ValueError("STAGING_PRICE_COUNT_MISMATCH")
        if con.execute("SELECT COUNT(*) FROM monthly_research_membership").fetchone()[0] != m["monthly_membership_rows"]:
            raise ValueError("STAGING_MONTH_COUNT_MISMATCH")
        if con.execute("SELECT COUNT(*) FROM candidate_gate").fetchone()[0] != m["phase25k_research_gate_rows"]:
            raise ValueError("STAGING_GATE_COUNT_MISMATCH")
        # Existing explicit immutable research-only gates may never be promoted.
        for table, col in (("candidate_gate", "canonical_approved"),
                           ("candidate_identity", "historical_CIK_identity_certified"),
                           ("source_daily_price", "source_adjustment_certified"),
                           ("source_daily_price", "historical_security_identity_certified")):
            if con.execute(f"SELECT COUNT(*) FROM {table} WHERE {col}!=0").fetchone()[0]:
                raise ValueError("UPSTREAM_RESEARCH_ONLY_GUARD_CHANGED")

        ranked = []
        for c in con.execute("SELECT simfin_id,ticker,priority,missing_evidence FROM candidate_gate"):
            sid, ticker = str(c["simfin_id"]), str(c["ticker"])
            n, lo, hi, listed = con.execute(
                "SELECT COUNT(*),MIN(trade_date),MAX(trade_date), "
                "COALESCE(SUM(listed_in_same_month_end_archive),0) "
                "FROM source_daily_price WHERE simfin_id=? AND ticker=?",
                (sid, ticker)).fetchone()
            months = con.execute(
                "SELECT COUNT(DISTINCT month_end) FROM monthly_research_membership WHERE ticker=?",
                (ticker,)).fetchone()[0]
            if ticker in risk_tickers:
                continue  # conflict symbols remain quarantined
            if n:
                ranked.append({
                    "simfin_id": sid, "ticker": ticker, "source_price_rows": n,
                    "listed_source_price_rows": int(listed),
                    "months_with_ticker_source_listing": int(months),
                    "first_source_price_date": lo, "last_source_price_date": hi,
                    "priority": c["priority"],
                    "canonical_issuer_identity_certified": False,
                    "adjusted_total_return_certified": False,
                    "canonical_admission": "BLOCKED_PIT_IDENTITY_ACTION_PRICE_AVAILABLE_AT",
                })
        ranked.sort(key=lambda x: (-x["source_price_rows"],
                                    -x["months_with_ticker_source_listing"],
                                    x["ticker"], x["simfin_id"]))
        pilot = ranked[:pilot_size]

    event_cases = [{
        "ticker": sym, "official_event_class": event[0],
        "official_research_source_urls": list(event[1]),
        "event_is_not_certified_price_or_2024_pit_identity": True,
        "quarantine_if_identity_collision": sym in risk_tickers,
    } for sym, event in OFFICIAL_CASES.items()]

    sitc = {"status": "NOT_PROVIDED", "pairs": None}
    if sitc_path is not None:
        a = _json(sitc_path)
        if (a.get("schema") != "MERIDYEN_PHASE25S_SITC_OFFICIAL_ACTION_SOURCE_PAIR_RESEARCH_V1"
            or a.get("research_staging_version") != m["staging_version"]
            or a.get("canonical_eligible_securities") != 0
            or a.get("corporate_action_vendor_adjusted_price_certified") != 0
            or a.get("issuer_documented_actions") != 2):
            raise ValueError("SITC_REPORT_UNTRUSTED_OR_STAGE_VERSION_MISMATCH")
        sitc = {"status": "TWO_OFFICIAL_EVENTS_RESEARCH_ONLY",
                "pairs": a.get("source_pair_diagnostics_computed", 0)}

    market = _probe_market(operational_db)
    return {
        "schema": SCHEMA,
        "status": "RESEARCH_PILOT_BUILT_CANONICAL_ADMISSION_BLOCKED",
        "source_staging_version": m["staging_version"],
        "period": WINDOW,
        "source_price_sha256": m["source_price_sha256"],
        "source_membership_rows": m["monthly_membership_rows"],
        "source_price_rows": m["source_daily_valid_price_rows"],
        "conflict_rows": 464, "conflict_ticker_strings": 30,
        "conflict_strong_tickers": list(STRONG_CONFLICTS),
        "conflict_quarantine_rows": [
            {**r, "resolution_status": "QUARANTINED_PENDING_DATED_IDENTITY_EVIDENCE"}
            for r in conflicts
        ],
        "conflict_rows_canonically_resolved": 0,
        "source_candidate_gate_rows": m["phase25k_research_gate_rows"],
        "nonconflicting_source_candidates_with_prices": len(ranked),
        "research_only_pilot_target": pilot_size,
        "research_only_pilot_selected": len(pilot),
        "pilot_candidates": pilot,
        "official_event_research_cases": event_cases,
        "sitc_pair_evidence": sitc,
        "operational_db_observation": market,
        "canonical_accepted_securities_proven": 0,
        "canonical_accepted_security_dates_proven": 0,
        "canonical_admission_justification": "NO_INDEPENDENT_HISTORICAL_PIT_IDENTITY_CA_PRICE_SEC_AVAILABLE_AT_CERTIFICATIONS",
        "remaining_global_blockers": list(BLOCKERS),
        "source_files_modified": False,
        "operational_db_modified": False,
        "wf9_or_learning_v3_executed": False,
    }


def main():
    root = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "S153ResearchTerminal/runtime"
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=root/"phase25q/staged_datasets/research_pit_28323984fb4f48b1/manifest.json")
    p.add_argument("--phase25r", type=Path, default=root/"phase25r/staging_readonly_reconciliation.json")
    p.add_argument("--sitc", type=Path, default=None)
    p.add_argument("--operational-db", type=Path, default=root/"data/runtime/operational.db")
    p.add_argument("--pilot-size", type=int, default=25)
    p.add_argument("--out", type=Path, default=root/"phase25w/pilot_cohort_research_only_v1.json")
    a = p.parse_args()
    try:
        sources = {x.resolve() for x in (a.manifest, a.phase25r, a.operational_db)}
        if a.sitc:
            sources.add(a.sitc.resolve())
        if a.out.is_symlink() or a.out.resolve() in sources or a.out.exists():
            raise ValueError("OUTPUT_NOT_NEW_OR_OVERLAPS_SOURCE")
        result = assess(a.manifest, a.phase25r, a.operational_db,
                        pilot_size=a.pilot_size, sitc_path=a.sitc)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(json.dumps({
            "status": result["status"],
            "research_only_pilot_selected": result["research_only_pilot_selected"],
            "identity_conflicts_quarantined": result["conflict_rows"],
            "canonical_accepted_securities_proven": 0,
            "operational_db_observation": result["operational_db_observation"],
            "sitc_pair_evidence": result["sitc_pair_evidence"],
            "private_report": str(a.out),
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        print("PHASE25W_BLOCKED: " + type(exc).__name__ + ": " + str(exc)[:110])
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

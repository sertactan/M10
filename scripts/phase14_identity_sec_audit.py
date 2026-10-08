from __future__ import annotations

"""Phase14 identity and SEC-as-of audit; strictly read-only on live SQLite.

This audit flags evidence gaps, not proven historical reassignments. A company
may change names/tickers, and different share classes may have the same CIK.
An SEC Companyfacts bulk archive has filing dates but (absent a matched SEC
submissions record) no authoritative acceptance timestamps. Consequently a
safe-looking row count MUST NOT be promoted to canonical PIT evidence.
"""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3

SCHEMA = "MERIDYEN_PHASE14_IDENTITY_SEC_TIMESTAMP_AUDIT_V1"
REQUIRED_TABLES = {
    "security_master",
    "universe_snapshot_membership",
    "ticker_aliases",
    "filing_records_source",
    "fundamental_facts_source",
}
MAX_SAMPLES = 30


def _iso(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _cik(value: object) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if not raw.isascii() or not raw.isdigit() or len(raw) > 10:
        return None
    return raw.zfill(10)


def _example(items: list, value: dict) -> None:
    if len(items) < MAX_SAMPLES:
        items.append(value)


def _overlap(a_start: str, a_end: str | None, b_start: str, b_end: str | None) -> bool:
    """Known bounded alias windows only. Unknown dates cannot prove overlap."""
    if not a_start or not b_start or not a_end or not b_end:
        return False
    return max(a_start, b_start) <= min(a_end, b_end)


def audit(db_path: Path, *, sec_sample: int = 2000) -> dict:
    if not 1 <= sec_sample <= 20_000:
        raise ValueError("--sec-sample must be 1..20000 to bound live DB impact")
    db = Path(db_path).expanduser().resolve()
    result = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(db),
        "status": "BLOCKED",
        "mode": "SQLITE_READ_ONLY_NO_NETWORK",
        "canonical_pit_identity_verified": False,
        "original_sec_filing_acceptance_verified": False,
        "wf9_activated": False,
        "errors": [],
        "warnings": [],
        "identity": {},
        "sec_timing": {},
    }
    if not db.is_file():
        result["errors"].append("LIVE_OPERATIONAL_DB_NOT_FOUND")
        return result
    # No AppContainer(), schema initialization, migrations, transactions,
    # PRAGMA quick_check, or VACUUM. Never write to the live SEC importer.
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=0.75)) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=750")
        tables = {
            str(row["name"]) for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            result["errors"].append("REQUIRED_TABLES_MISSING")
            result["missing_tables"] = missing
            return result

        # 1. Issuer identity conflicts: different known CIKs under one
        # ticker+exchange are a RE-USE/RISK signal, not proof of bad assignment.
        # Same-CIK multi-class securities are not automatically merged.
        securities = con.execute(
            """SELECT security_id,ticker,exchange,cik
               FROM security_master WHERE market='US'
                 AND exchange IN ('NASDAQ','NYSE','AMEX')"""
        ).fetchall()
        by_ticker: dict[tuple[str, str], list[tuple[str, str | None]]] = defaultdict(list)
        invalid_cik_examples: list[dict] = []
        invalid_cik_count = 0
        for row in securities:
            raw = row["cik"]
            normalized = _cik(raw)
            if raw not in (None, "") and normalized is None:
                invalid_cik_count += 1
                _example(invalid_cik_examples, {
                    "security_id": row["security_id"], "ticker": row["ticker"],
                    "exchange": row["exchange"],
                })
            by_ticker[(str(row["ticker"]).upper(), str(row["exchange"]))].append(
                (str(row["security_id"]), normalized)
            )
        reused_examples: list[dict] = []
        reused = 0
        for (ticker, exchange), members in sorted(by_ticker.items()):
            distinct = {cik for _, cik in members if cik}
            if len(distinct) > 1:
                reused += 1
                _example(reused_examples, {
                    "ticker": ticker, "exchange": exchange,
                    "security_ids": sorted({sid for sid, _ in members})[:8],
                    "distinct_ciks": sorted(distinct)[:8],
                })

        # 2. One ticker/exchange/date appearing under two security IDs is
        # dangerous for as-of joins regardless of current master ticker.
        duplicate_snapshot_groups = con.execute(
            """SELECT snapshot_date,ticker,exchange,
                      COUNT(DISTINCT security_id) AS security_ids
               FROM universe_snapshot_membership
               GROUP BY snapshot_date,ticker,exchange
               HAVING COUNT(DISTINCT security_id)>1
               ORDER BY snapshot_date,ticker,exchange
               LIMIT 31"""
        ).fetchall()
        # Note: this is bounded to 31 for speed; count must not be advertised
        # as an exhaustive total if overflow occurs.
        # 3. Explicit ticker aliases with KNOWN overlapping date ranges
        # belonging to different security IDs.
        aliases = con.execute(
            """SELECT alias,security_id,valid_from,valid_to
               FROM ticker_aliases
               WHERE valid_from <> '' AND valid_to IS NOT NULL
               ORDER BY alias,valid_from"""
        ).fetchall()
        by_alias: dict[str, list] = defaultdict(list)
        for row in aliases:
            by_alias[str(row["alias"]).upper()].append(row)
        overlaps: list[dict] = []
        overlap_count = 0
        for alias, members in by_alias.items():
            for i, first in enumerate(members):
                for second in members[i + 1:]:
                    if first["security_id"] == second["security_id"]:
                        continue
                    if _overlap(str(first["valid_from"]), str(first["valid_to"]),
                                str(second["valid_from"]), str(second["valid_to"])):
                        overlap_count += 1
                        _example(overlaps, {
                            "alias": alias,
                            "security_ids": [first["security_id"], second["security_id"]],
                            "overlap_start": max(first["valid_from"], second["valid_from"]),
                            "overlap_end": min(first["valid_to"], second["valid_to"]),
                        })
        result["identity"] = {
            "us_security_master_rows_examined": len(securities),
            "distinct_ticker_exchange_keys": len(by_ticker),
            "ticker_exchange_keys_with_distinct_known_ciks": reused,
            "ticker_reuse_candidates": reused_examples,
            "malformed_nonempty_cik_count": invalid_cik_count,
            "malformed_cik_examples": invalid_cik_examples,
            "simultaneous_snapshot_identity_collision_count_lower_bound":
                min(len(duplicate_snapshot_groups), 30),
            "simultaneous_collision_examples": [
                dict(row) for row in duplicate_snapshot_groups[:MAX_SAMPLES]
            ],
            "simultaneous_collision_result_truncated": len(duplicate_snapshot_groups) > 30,
            "dated_alias_overlap_pairs": overlap_count,
            "dated_alias_overlap_examples": overlaps,
            "undated_or_open_ended_alias_overlap_not_certified": True,
        }
        if reused:
            result["warnings"].append("TICKER_REUSE_DISTINCT_CIK_NEEDS_HISTORICAL_RECONCILIATION")
        if invalid_cik_count:
            result["warnings"].append("MALFORMED_CIK_VALUES")
        if duplicate_snapshot_groups:
            result["errors"].append("SAME_SNAPSHOT_TICKER_MULTIPLE_SECURITY_IDS")
        if overlap_count:
            result["warnings"].append("OVERLAPPING_DATED_TICKER_ALIASES_NEED_REVIEW")

        # 4. Sample LATEST SEC rows by descending rowid so the audit does not
        # COUNT or sort a multi-million row fact archive during live import.
        # The sample is intentionally BIASED and never an all-period assurance.
        facts = con.execute(
            """SELECT fact_id,security_id,accession_number,period_end,
                      filing_date,accepted_at,available_at,retrieved_at
               FROM fundamental_facts_source
               WHERE source='SEC_EDGAR'
               ORDER BY rowid DESC LIMIT ?""",
            (sec_sample,),
        ).fetchall()
        counts: dict[str, int] = defaultdict(int)
        examples: dict[str, list[dict]] = defaultdict(list)
        # filing lookup index: (security_id,accession_number,source)
        for fact in facts:
            sid = str(fact["security_id"])
            accession = fact["accession_number"]
            fact_id = str(fact["fact_id"])
            accepted_text = fact["accepted_at"]
            available_text = fact["available_at"]
            accepted = _iso(accepted_text)
            available = _iso(available_text)
            evidence = {"fact_id": fact_id, "security_id": sid,
                        "accession_number": accession}
            def flag(code: str) -> None:
                counts[code] += 1
                _example(examples[code], evidence)

            if accepted_text in ("", None):
                flag("FACT_ACCEPTANCE_TIMESTAMP_MISSING")
            elif accepted is None:
                flag("FACT_ACCEPTANCE_TIMESTAMP_INVALID_OR_NAIVE")
            if available is None:
                flag("FACT_AVAILABLE_AT_INVALID_OR_NAIVE")
            if accepted and available and available < accepted:
                flag("FACT_AVAILABLE_BEFORE_ACCEPTANCE")
            try:
                filing_date = date.fromisoformat(str(fact["filing_date"])) if fact["filing_date"] else None
            except ValueError:
                filing_date = None
                flag("FACT_FILING_DATE_INVALID")
            if filing_date and available and available.date() < filing_date:
                flag("FACT_AVAILABLE_BEFORE_FILED_DATE")
            if filing_date and fact["period_end"]:
                try:
                    if date.fromisoformat(str(fact["period_end"])) > filing_date:
                        flag("FACT_PERIOD_END_AFTER_FILING")
                except ValueError:
                    flag("FACT_PERIOD_END_INVALID")
            if not accession:
                flag("FACT_ACCESSION_MISSING")
                continue
            filings = con.execute(
                """SELECT accepted_at,cik,filing_date
                   FROM filing_records_source WHERE
                   security_id=? AND accession_number=? AND source='SEC_EDGAR'
                   LIMIT 2""",
                (sid, accession),
            ).fetchall()
            if len(filings) > 1:
                flag("FACT_ACCESSION_AMBIGUOUS_IN_FILINGS")
                continue
            if not filings:
                flag("FACT_ACCESSION_NOT_LINKED_TO_SEC_SUBMISSIONS")
                continue
            linked = _iso(filings[0]["accepted_at"])
            if linked is None:
                flag("LINKED_FILING_ACCEPTANCE_MISSING")
            elif available and available < linked:
                flag("FACT_AVAILABLE_BEFORE_LINKED_FILING_ACCEPTANCE")
            elif accepted is None:
                flag("FACT_ACCEPTANCE_MISSING_BUT_LINKED_FILING_HAS_IT")
            elif abs((accepted - linked).total_seconds()) > 60:
                flag("FACT_ACCEPTANCE_MISMATCH_WITH_LINKED_FILING")

        result["sec_timing"] = {
            "latest_rows_sampled": len(facts),
            "max_sample": sec_sample,
            "sample_method": "SEC_EDGAR_FACT_ROWS_REVERSE_ROWID_NOT_RANDOM_NOT_EXHAUSTIVE",
            "issues_in_sample": dict(sorted(counts.items())),
            "issue_examples": dict(examples),
            "sec_original_acceptance_audit_complete": False,
            "sec_companyfacts_zip_filing_only_not_equivalent_to_submissions": True,
        }
        dangerous = {
            "FACT_AVAILABLE_BEFORE_ACCEPTANCE",
            "FACT_AVAILABLE_BEFORE_FILED_DATE",
            "FACT_AVAILABLE_BEFORE_LINKED_FILING_ACCEPTANCE",
            "FACT_ACCEPTANCE_MISMATCH_WITH_LINKED_FILING",
            "FACT_PERIOD_END_AFTER_FILING",
        }
        if any(counts.get(key) for key in dangerous):
            result["errors"].append("SEC_TIME_INTEGRITY_CONFLICT_IN_SAMPLED_FACTS")
        if any(counts.get(key) for key in (
            "FACT_ACCEPTANCE_TIMESTAMP_MISSING",
            "FACT_ACCEPTANCE_TIMESTAMP_INVALID_OR_NAIVE",
            "FACT_AVAILABLE_AT_INVALID_OR_NAIVE",
            "FACT_ACCESSION_MISSING",
            "FACT_ACCESSION_NOT_LINKED_TO_SEC_SUBMISSIONS",
            "LINKED_FILING_ACCEPTANCE_MISSING",
        )):
            result["warnings"].append("ORIGINAL_SEC_ACCEPTANCE_EVIDENCE_INCOMPLETE")

    result["errors"] = sorted(set(result["errors"]))
    result["warnings"] = sorted(set(result["warnings"]))
    result["status"] = (
        "IDENTITY_OR_TEMPORAL_CONFLICTS_REQUIRE_REVIEW" if result["errors"]
        else "EVIDENCE_GAPS_REQUIRE_RECONCILIATION" if result["warnings"]
        else "SAMPLED_NO_FLAGS_NOT_PIT_CERTIFIED"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path,
                        help="Actual installed M10 operational.db (read-only)")
    parser.add_argument("--sec-sample", type=int, default=2000,
                        help="Latest N SEC facts (1..20000); biased non-exhaustive")
    parser.add_argument("--out", type=Path, default=None,
                        help="Optional JSON report destination OUTSIDE the live DB")
    args = parser.parse_args()
    try:
        report = audit(args.db, sec_sample=args.sec_sample)
        encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        print(encoded)
        if args.out:
            dest = args.out.expanduser().resolve()
            if dest == args.db.expanduser().resolve():
                raise ValueError("Cannot overwrite database with report")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(encoded, encoding="utf-8")
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, "PHASE14_IDENTITY_SEC_AUDIT_BLOCKED: "
                    + type(exc).__name__ + "\n")
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

"""Stage SEC original acceptance evidence; never mutate the live M10 database.

Inputs are locally saved *original* SEC submissions JSON. Their source hash is
preserved; external file provenance is not proved by a hash alone. No network
requests, no SQLite schema creation, no UPDATE, and no false PIT promotion.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

SCHEMA = "MERIDYEN_SEC_SUBMISSIONS_ACCEPTANCE_STAGE_V1"
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
MAX_INPUT_BYTES = 20_000_000
MAX_EXAMPLES = 25


def normalize_cik(value: object) -> str:
    value = str(value).strip()
    if not value or not value.isascii() or not value.isdigit() or len(value) > 10:
        raise ValueError("Invalid CIK in SEC submissions payload")
    return value.zfill(10)


def exact_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        timestamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return None
    return timestamp.astimezone(timezone.utc)


def filing_rows(payload: dict) -> list[dict]:
    block = payload.get("filings", {}).get("recent") if "filings" in payload else payload
    if not isinstance(block, dict):
        raise ValueError("Missing submissions filings.recent object")
    accessions = block.get("accessionNumber", [])
    accepted = block.get("acceptanceDateTime", [])
    forms = block.get("form", [])
    dates = block.get("filingDate", [])
    if not all(isinstance(v, list) for v in (accessions, accepted, forms, dates)):
        raise ValueError("Invalid submissions arrays")
    if not (len(accessions) == len(accepted) == len(forms) == len(dates)):
        raise ValueError("Misaligned SEC submissions arrays")
    return [
        {
            "accession": str(accessions[i]),
            "accepted": accepted[i],
            "form": str(forms[i]),
            "filing_date": dates[i],
        }
        for i in range(len(accessions))
    ]


def stage(db_path: Path, input_path: Path, *, max_facts: int = 2000) -> dict:
    if not 1 <= max_facts <= 20_000:
        raise ValueError("max_facts must be 1..20000")
    if input_path.is_symlink() or not input_path.is_file():
        raise ValueError("Existing regular SEC submissions JSON input required")
    if input_path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("SEC submissions file exceeds the configured size cap")
    payload_bytes = input_path.read_bytes()
    payload = json.loads(payload_bytes)
    if not isinstance(payload, dict):
        raise ValueError("Invalid SEC submissions payload")
    cik = normalize_cik(payload.get("cik"))
    entries = filing_rows(payload)
    path = db_path.expanduser().resolve()
    if not path.is_file() or path.is_symlink():
        raise ValueError("Actual installed operational.db must exist; will not create")
    report = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(path),
        "source_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "input_file": str(input_path.resolve()),
        "SEC_submissions_cik": cik,
        "mode": "READ_ONLY_STAGING_NO_DATABASE_WRITES",
        "source_authenticity_independently_verified": False,
        "original_acceptance_evidence_complete": False,
        "historical_pit_certified": False,
        "wf9_activated": False,
        "status": "REQUIRES_REVIEW",
        "counts": {},
        "staged": [],
    }
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.75)) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=750")
        matches = con.execute(
            "SELECT security_id,cik FROM security_master WHERE cik IS NOT NULL"
        ).fetchall()
        security_ids = sorted({
            row["security_id"] for row in matches if
            str(row["cik"]).strip().isascii() and
            str(row["cik"]).strip().isdigit() and
            str(row["cik"]).strip().zfill(10) == cik
        })
        report["matched_security_ids"] = security_ids[:MAX_EXAMPLES]
        report["matched_security_count"] = len(security_ids)
        if len(security_ids) != 1:
            report["status"] = "BLOCKED_CIK_IDENTITY_AMBIGUOUS"
            return report
        security_id = security_ids[0]
        counters: Counter[str] = Counter()
        by_accession: dict[str, dict] = {}
        for row in entries:
            accession = row["accession"]
            if not ACCESSION.fullmatch(accession):
                counters["invalid_accession_format"] += 1
                continue
            accepted_at = exact_utc(row["accepted"])
            if accepted_at is None:
                counters["no_authoritative_offset_aware_acceptance"] += 1
                continue
            try:
                filing_date = datetime.strptime(str(row["filing_date"]), "%Y-%m-%d").date()
            except ValueError:
                counters["invalid_filing_date"] += 1
                continue
            if accepted_at.date() < filing_date:
                counters["acceptance_date_before_filing_date"] += 1
                continue
            existing = by_accession.get(accession)
            if existing and existing["accepted_at"] != accepted_at.isoformat():
                counters["conflicting_sec_accession_acceptance"] += 1
                by_accession.pop(accession)
                continue
            by_accession[accession] = {
                "accession_number": accession, "accepted_at": accepted_at.isoformat(),
                "form": row["form"], "filing_date": filing_date.isoformat(),
            }

        for accession, source in sorted(by_accession.items()):
            facts = con.execute(
                """SELECT fact_id,accepted_at,available_at,filing_date
                   FROM fundamental_facts_source
                   WHERE source='SEC_EDGAR' AND security_id=? AND accession_number=?
                   ORDER BY rowid DESC LIMIT ?""",
                (security_id, accession, max_facts + 1),
            ).fetchall()
            if not facts:
                counters["accessions_without_facts"] += 1
                continue
            if len(facts) > max_facts:
                counters["accessions_truncated_fail_closed"] += 1
                continue
            accepted_at = exact_utc(source["accepted_at"])
            assert accepted_at is not None
            # Keep records individually bounded. Never lower a later
            # conservative availability or overwrite original rows here.
            for fact in facts:
                stored_accepted = exact_utc(fact["accepted_at"])
                availability = exact_utc(fact["available_at"])
                if availability is None:
                    counters["malformed_fact_availability"] += 1
                    continue
                if stored_accepted is not None and stored_accepted != accepted_at:
                    counters["conflicting_existing_acceptance"] += 1
                    continue
                try:
                    stored_filing = datetime.strptime(
                        str(fact["filing_date"]), "%Y-%m-%d"
                    ).date()
                except ValueError:
                    counters["invalid_fact_filing_date"] += 1
                    continue
                if stored_filing != datetime.strptime(source["filing_date"], "%Y-%m-%d").date():
                    counters["fact_filing_date_mismatch"] += 1
                    continue
                if availability < accepted_at:
                    counters["lookahead_available_before_accepted"] += 1
                    continue
                counters["evidence_rows_staged"] += 1
                if len(report["staged"]) < MAX_EXAMPLES:
                    report["staged"].append({
                        "fact_id": fact["fact_id"],
                        "security_id": security_id,
                        "accession_number": accession,
                        "sec_accepted_at": accepted_at.isoformat(),
                        "stored_accepted_at": fact["accepted_at"],
                        "stored_available_at": fact["available_at"],
                        "eligible_for_later_review": stored_accepted is None,
                    })
        report["counts"] = dict(sorted(counters.items()))
        report["status"] = (
            "EVIDENCE_STAGED_REVIEW_REQUIRED"
            if counters.get("evidence_rows_staged", 0)
            else "NO_SAFE_MATCHES_REQUIRE_REVIEW"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--submissions-json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-facts-per-accession", type=int, default=2000)
    args = parser.parse_args()
    try:
        report = stage(
            args.db, args.submissions_json,
            max_facts=args.max_facts_per_accession,
        )
        output = args.out.expanduser().resolve()
        if output == args.db.expanduser().resolve() or output == args.submissions_json.expanduser().resolve():
            raise ValueError("Report path must not overwrite live DB or SEC source JSON")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": report["status"],
            "matched_security_count": report.get("matched_security_count"),
            "counts": report["counts"],
            "report": str(output),
            "database_modified": False,
        }, ensure_ascii=False))
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, "SEC_ACCEPTANCE_STAGE_BLOCKED: " + type(exc).__name__ + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

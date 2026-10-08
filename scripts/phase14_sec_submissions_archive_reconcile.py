from __future__ import annotations

"""Bounded offline SEC submissions history -> M10 fact acceptance evidence.

SEC root CIK*.json refers to older filings.files archive documents.
No network, migrations, API credentials, live DB writes or canonical promotion.
Use a verified SQLite backup and downloaded ORIGINAL SEC submissions files.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from scripts.phase14_sec_acceptance_stage import (
    ACCESSION, MAX_INPUT_BYTES, exact_utc, filing_rows, normalize_cik,
)

SCHEMA = "MERIDYEN_SEC_SUBMISSIONS_ARCHIVE_RECONCILIATION_V1"
ROOT_FILE = re.compile(r"^CIK(\d{10})\.json$")
MAX_EXAMPLES = 30
NEEDED_FACT_COLUMNS = {
    "fact_id", "security_id", "accession_number", "source", "accepted_at",
    "available_at", "filing_date", "form_type", "period_end",
}


def _read_json(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("SEC source must be an existing non-symlink file")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("SEC submissions source too large")
    raw = path.read_bytes()
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("SEC JSON must be an object")
    return obj, hashlib.sha256(raw).hexdigest()


def _source_rows(folder: Path, root: Path, cik: str, counters: Counter):
    payload, digest = _read_json(root)
    if normalize_cik(payload.get("cik")) != cik:
        raise ValueError("SEC root document CIK disagrees with filename")
    filings = payload.get("filings")
    if not isinstance(filings, dict):
        raise ValueError("Root SEC submissions filings object missing")
    yield root.name, digest, filing_rows({"filings": {"recent": filings.get("recent")}})
    archived = filings.get("files", [])
    if not isinstance(archived, list):
        raise ValueError("SEC filings.files must be an array")
    seen: set[str] = set()
    for item in archived:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("Invalid SEC archival filename metadata")
        name = item["name"]
        # Filenames must be exact; no traversal, arbitrary sibling sources or
        # misleading archive from a DIFFERENT CIK.
        if not re.fullmatch(rf"CIK{cik}-submissions-\d{{3,}}\.json", name):
            raise ValueError("SEC archive name is not valid for issuer CIK")
        if name in seen:
            counters["duplicate_archive_manifest_names"] += 1
            continue
        seen.add(name)
        src = folder / name
        if not src.is_file():
            counters["missing_archival_documents"] += 1
            continue
        history, source_digest = _read_json(src)
        if "cik" in history and normalize_cik(history["cik"]) != cik:
            raise ValueError("SEC archive CIK disagrees with root")
        counters["archival_documents_loaded"] += 1
        yield name, source_digest, filing_rows(history)


def _issuer_index(connection: sqlite3.Connection) -> dict[str, set[str]]:
    mapped: dict[str, set[str]] = defaultdict(set)
    for security_id, raw in connection.execute(
        "SELECT security_id,cik FROM security_master WHERE cik IS NOT NULL"
    ):
        try:
            cik = normalize_cik(raw)
        except ValueError:
            continue
        mapped[cik].add(str(security_id))
    return mapped


def reconcile(db: Path, folder: Path, *, max_issuers: int = 5,
              max_accessions: int = 1000, max_facts: int = 2000) -> dict:
    if not (1 <= max_issuers <= 100 and 1 <= max_accessions <= 50_000
            and 1 <= max_facts <= 20_000):
        raise ValueError("Unbounded SEC reconciliation is not permitted")
    if db.is_symlink() or not db.is_file():
        raise ValueError("Existing SQLite backup required; never create a new DB")
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Existing non-symlink SEC source directory required")
    roots = sorted(
        p for p in folder.iterdir() if ROOT_FILE.fullmatch(p.name)
    )
    if not roots:
        raise ValueError("No CIK##########.json SEC root documents found")

    report = {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "OFFLINE_SQLITE_READ_ONLY_NO_NETWORK_NO_CANONICAL_WRITE",
        "database": str(db.resolve()),
        "submissions_dir": str(folder.resolve()),
        "status": "REVIEW_REQUIRED",
        "all_available_issuers_scanned": len(roots) <= max_issuers,
        "archival_coverage_complete": False,
        "independent_sec_download_provenance_verified": False,
        "historical_pit_certified": False,
        "wf9_activated": False,
        "database_modified": False,
        "counts": {},
        "evidence_candidates": [],
        "conflicts": [],
    }
    counts: Counter[str] = Counter()
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro",
                                 uri=True, timeout=2)) as con:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=2000")
        cols = {row["name"] for row in con.execute(
            "PRAGMA table_info(fundamental_facts_source)"
        )}
        if not NEEDED_FACT_COLUMNS.issubset(cols):
            report["status"] = "BLOCKED_FACT_SCHEMA_INCOMPLETE"
            return report
        indices = {row["name"] for row in con.execute(
            "PRAGMA index_list(fundamental_facts_source)"
        )}
        if "idx_fundamental_accession" not in indices:
            report["status"] = "BLOCKED_ACCESSION_INDEX_MISSING"
            return report
        mapped = _issuer_index(con)
        valid_accessions: dict[tuple[str, str], dict] = {}
        conflicting: set[tuple[str, str]] = set()

        for root in roots[:max_issuers]:
            counts["issuer_root_documents_loaded"] += 1
            cik = ROOT_FILE.fullmatch(root.name).group(1)
            ids = mapped.get(cik, set())
            if len(ids) != 1:
                counts["issuer_identity_ambiguous_or_missing"] += 1
                if len(report["conflicts"]) < MAX_EXAMPLES:
                    report["conflicts"].append({
                        "cik": cik, "reason": "CIK_NOT_UNIQUE_TO_ONE_SECURITY",
                        "matched_security_count": len(ids),
                    })
                continue
            for source_name, source_hash, rows in _source_rows(
                folder, root, cik, counts
            ):
                for entry in rows:
                    acc = entry["accession"]
                    if not ACCESSION.fullmatch(acc):
                        counts["invalid_accession"] += 1
                        continue
                    key = (cik, acc)
                    accepted = exact_utc(entry["accepted"])
                    if accepted is None:
                        counts["acceptance_missing_offset"] += 1
                        conflicting.add(key)
                        valid_accessions.pop(key, None)
                        continue
                    try:
                        filed = date.fromisoformat(str(entry["filing_date"]))
                    except ValueError:
                        counts["invalid_filing_date"] += 1
                        conflicting.add(key)
                        valid_accessions.pop(key, None)
                        continue
                    if accepted.date() < filed:
                        counts["acceptance_before_filing_date"] += 1
                        conflicting.add(key)
                        valid_accessions.pop(key, None)
                        continue
                    value = {
                        "cik": cik, "security_id": next(iter(ids)),
                        "accession_number": acc,
                        "sec_accepted_at": accepted.isoformat(),
                        "filing_date": filed.isoformat(),
                        "form": entry["form"],
                        "source_filename": source_name,
                        "source_sha256": source_hash,
                    }
                    prev = valid_accessions.get(key)
                    if key in conflicting:
                        continue
                    if prev and any(prev[k] != value[k] for k in (
                            "sec_accepted_at", "filing_date", "form")):
                        counts["conflicting_duplicate_accessions"] += 1
                        conflicting.add(key)
                        del valid_accessions[key]
                    elif not prev:
                        valid_accessions[key] = value
                    else:
                        counts["identical_duplicate_accession"] += 1
        # Global cap bounds indexed DB work. Excess MUST be explicitly flagged.
        ordered = sorted(valid_accessions.values(), key=lambda v: (
            v["filing_date"], v["cik"], v["accession_number"]))
        if len(ordered) > max_accessions:
            counts["accessions_deferred_by_run_limit"] = len(ordered) - max_accessions
        for entry in ordered[:max_accessions]:
            rows = con.execute(
                """SELECT fact_id,accepted_at,available_at,filing_date,
                          period_end,form_type FROM fundamental_facts_source
                   WHERE source='SEC_EDGAR' AND security_id=? AND accession_number=?
                   LIMIT ?""",
                (entry["security_id"], entry["accession_number"], max_facts + 1),
            ).fetchall()
            if not rows:
                counts["accessions_without_matching_facts"] += 1
                continue
            if len(rows) > max_facts:
                counts["accessions_exceed_fact_limit"] += 1
                continue
            sec_time = exact_utc(entry["sec_accepted_at"])
            bad_reasons: set[str] = set()
            for fact in rows:
                av = exact_utc(fact["available_at"])
                raw_acc = fact["accepted_at"]
                known = exact_utc(raw_acc)
                if av is None:
                    bad_reasons.add("FACT_AVAILABILITY_INVALID")
                elif av < sec_time:
                    bad_reasons.add("AVAILABLE_BEFORE_SEC_ACCEPTANCE")
                if raw_acc not in (None, "") and known is None:
                    bad_reasons.add("STORED_ACCEPTANCE_MALFORMED")
                if known is not None and known != sec_time:
                    bad_reasons.add("CONFLICT_WITH_STORED_ACCEPTANCE")
                if str(fact["filing_date"]) != entry["filing_date"]:
                    bad_reasons.add("FACT_FILING_DATE_MISMATCH")
                if fact["form_type"] and str(fact["form_type"]) != entry["form"]:
                    bad_reasons.add("FACT_FORM_MISMATCH")
                if fact["period_end"] and str(fact["period_end"]) > entry["filing_date"]:
                    bad_reasons.add("FUTURE_FACT_PERIOD")
            if bad_reasons:
                for reason in sorted(bad_reasons):
                    counts["rejected_" + reason.lower()] += 1
                if len(report["conflicts"]) < MAX_EXAMPLES:
                    report["conflicts"].append({
                        "cik": entry["cik"],
                        "accession_number": entry["accession_number"],
                        "reasons": sorted(bad_reasons),
                    })
                continue
            counts["accessions_with_reviewable_evidence"] += 1
            counts["facts_with_reviewable_evidence"] += len(rows)
            entry["matched_facts"] = len(rows)
            # A deterministic accession-level review index; original fact
            # records are NOT modified and no per-fact approval is implied.
            report["evidence_candidates"].append(entry)
    counts["valid_accessions_indexed"] = len(valid_accessions)
    report["counts"] = dict(sorted(counts.items()))
    report["archival_coverage_complete"] = (
        counts["missing_archival_documents"] == 0
        and report["all_available_issuers_scanned"]
    )
    report["status"] = (
        "EVIDENCE_CANDIDATES_REVIEW_REQUIRED"
        if report["evidence_candidates"] else
        "NO_SAFE_MATCHING_EVIDENCE"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True,
                        help="Verified offline SQLite backup, NOT live SEC importer DB")
    parser.add_argument("--submissions-dir", type=Path, required=True,
                        help="Locally saved SEC root and historical filings.files JSONs")
    parser.add_argument("--out", type=Path, required=True,
                        help="Private JSON review report; must be outside SEC input folder")
    parser.add_argument("--max-issuers", type=int, default=5)
    parser.add_argument("--max-accessions", type=int, default=1000)
    parser.add_argument("--max-facts-per-accession", type=int, default=2000)
    args = parser.parse_args()
    try:
        db = args.db.expanduser().resolve()
        src = args.submissions_dir.expanduser().resolve()
        dest = args.out.expanduser().resolve()
        if dest == db or dest == src or src in dest.parents:
            raise ValueError("Report cannot overwrite DB or SEC input directory")
        result = reconcile(args.db, args.submissions_dir,
                           max_issuers=args.max_issuers,
                           max_accessions=args.max_accessions,
                           max_facts=args.max_facts_per_accession)
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            temp.write_text(json.dumps(result, indent=2, ensure_ascii=False)
                            + "\n", encoding="utf-8")
            temp.replace(dest)
        finally:
            temp.unlink(missing_ok=True)
        print(json.dumps({
            "status": result["status"],
            "counts": result["counts"],
            "archival_coverage_complete": result["archival_coverage_complete"],
            "report": str(dest),
            "database_modified": False,
        }, ensure_ascii=False))
    except (OSError, ValueError, TypeError, sqlite3.Error, json.JSONDecodeError) as exc:
        parser.exit(2, "SEC_SUBMISSIONS_ARCHIVE_BLOCKED: " + type(exc).__name__ + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

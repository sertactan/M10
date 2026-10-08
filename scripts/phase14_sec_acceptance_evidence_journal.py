from __future__ import annotations

"""Stage SEC acceptance evidence in a SEPARATE immutable SQLite review ledger.

Does NOT alter the live/imported operational DB, certify original filing times,
adjust available_at, or activate canonical models. Reads a verified DB backup,
local original SEC submissions, and the collector's SHA256 manifest.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from scripts.phase14_sec_submissions_archive_reconcile import reconcile
from scripts.phase14_sec_submissions_collect import ARCHIVE, ROOT, HOST, SCHEMA as COLLECTOR_SCHEMA

SCHEMA = "MERIDYEN_SEC_ACCEPTANCE_EVIDENCE_JOURNAL_V1"
STAGE = "STAGED_FOR_MANUAL_REVIEW_NOT_CANONICAL"
ALLOWED_ORIGIN = "FETCHED_FROM_PINNED_SEC_HTTPS_ENDPOINT"
DOC_LIMIT = 5_000_000

CREATE_EVIDENCE = """
CREATE TABLE IF NOT EXISTS sec_acceptance_evidence (
    cik TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    security_id TEXT NOT NULL,
    sec_accepted_at TEXT NOT NULL,
    filing_date TEXT NOT NULL,
    form TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    origin TEXT NOT NULL,
    source_retrieved_at_utc TEXT NOT NULL,
    backup_file TEXT NOT NULL,
    backup_size_bytes INTEGER NOT NULL,
    backup_mtime_ns INTEGER NOT NULL,
    matched_facts INTEGER NOT NULL,
    stage_status TEXT NOT NULL,
    inserted_at_utc TEXT NOT NULL,
    PRIMARY KEY(cik, accession_number, security_id)
)
"""
CREATE_RUN = """
CREATE TABLE IF NOT EXISTS sec_acceptance_staging_runs (
    run_id TEXT PRIMARY KEY,
    executed_at_utc TEXT NOT NULL,
    issuer_offset INTEGER NOT NULL,
    accession_offset INTEGER NOT NULL,
    candidate_count INTEGER NOT NULL,
    new_rows INTEGER NOT NULL,
    reused_rows INTEGER NOT NULL,
    missing_archive_documents INTEGER NOT NULL,
    note TEXT NOT NULL
)
"""
REQUIRED_COLS = {
    "cik", "accession_number", "security_id", "sec_accepted_at",
    "filing_date", "form", "source_filename", "source_sha256",
    "origin", "source_retrieved_at_utc", "backup_file",
    "backup_size_bytes", "backup_mtime_ns", "matched_facts",
    "stage_status", "inserted_at_utc",
}


class EvidenceBlocked(ValueError):
    pass


def _private_journal_path(db: Path, sources: Path, journal: Path) -> Path:
    if journal.is_symlink():
        raise EvidenceBlocked("EVIDENCE_JOURNAL_SYMLINK_NOT_ALLOWED")
    out = journal.expanduser().resolve()
    root = sources.expanduser().resolve()
    backup = db.expanduser().resolve()
    if out == backup or out == root or root in out.parents:
        raise EvidenceBlocked("EVIDENCE_JOURNAL_OVERLAPS_SEC_SOURCE_OR_DB")
    if out.suffix.lower() not in (".db", ".sqlite3"):
        raise EvidenceBlocked("EVIDENCE_JOURNAL_EXTENSION_INVALID")
    if out.exists() and not out.is_file():
        raise EvidenceBlocked("EVIDENCE_JOURNAL_NOT_A_FILE")
    if any((p / ".git").is_dir() for p in (out.parent, *out.parents)):
        raise EvidenceBlocked("EVIDENCE_JOURNAL_MUST_BE_OUTSIDE_GIT")
    return out


def _load_collector_manifest(folder: Path) -> dict:
    path = folder / "sec_sources_manifest.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > DOC_LIMIT:
        raise EvidenceBlocked("SEC_MANIFEST_MISSING_OR_UNSAFE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise EvidenceBlocked("SEC_MANIFEST_INVALID") from exc
    if (not isinstance(data, dict) or data.get("schema") != COLLECTOR_SCHEMA
            or not isinstance(data.get("documents"), dict)):
        raise EvidenceBlocked("SEC_MANIFEST_SCHEMA_INVALID")
    return data["documents"]


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_one_source(entry: dict, folder: Path, manifest: dict) -> dict:
    name = entry["source_filename"]
    cik = entry["cik"]
    # Restrict both source filenames and their CIK against accession evidence.
    match = ROOT.fullmatch(name) or ARCHIVE.fullmatch(name)
    if not match or match.group(1) != cik:
        raise EvidenceBlocked("SEC_EVIDENCE_SOURCE_NAME_MISMATCH")
    file = folder / name
    if file.is_symlink() or not file.is_file():
        raise EvidenceBlocked("SEC_EVIDENCE_SOURCE_FILE_MISSING")
    record = manifest.get(name)
    if not isinstance(record, dict):
        raise EvidenceBlocked("SEC_EVIDENCE_SOURCE_NOT_IN_MANIFEST")
    if record.get("origin") != ALLOWED_ORIGIN:
        raise EvidenceBlocked("SEC_EVIDENCE_PREEXISTING_SOURCE_UNVERIFIED")
    if record.get("url") != HOST + name:
        raise EvidenceBlocked("SEC_EVIDENCE_SOURCE_URL_MISMATCH")
    if record.get("source_authenticity_independently_verified") is not False:
        raise EvidenceBlocked("SEC_EVIDENCE_PROVENANCE_FLAG_INVALID")
    recorded_hash = record.get("sha256")
    expected = entry.get("source_sha256")
    if not (isinstance(recorded_hash, str) and re.fullmatch(r"[0-9a-f]{64}", recorded_hash)
            and expected == recorded_hash
            and recorded_hash == _file_sha256(file)):
        raise EvidenceBlocked("SEC_EVIDENCE_SOURCE_HASH_MISMATCH")
    if file.stat().st_size != record.get("size_bytes"):
        raise EvidenceBlocked("SEC_EVIDENCE_SOURCE_SIZE_MISMATCH")
    retrieved = record.get("retrieved_at_utc")
    if not isinstance(retrieved, str):
        raise EvidenceBlocked("SEC_EVIDENCE_SOURCE_RETRIEVAL_TIME_MISSING")
    try:
        at = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        if at.tzinfo is None:
            raise ValueError
    except ValueError as exc:
        raise EvidenceBlocked("SEC_EVIDENCE_SOURCE_RETRIEVAL_TIME_INVALID") from exc
    return record


def _evidence_rows(report: dict, db: Path, source_dir: Path) -> list[tuple]:
    docs = report["evidence_candidates"]
    if not docs:
        return []
    manifest = _load_collector_manifest(source_dir)
    st = db.stat()
    checked_sources: dict[str, dict] = {}
    rows: list[tuple] = []
    for item in docs:
        if item["source_filename"] not in checked_sources:
            checked_sources[item["source_filename"]] = _verify_one_source(
                item, source_dir, manifest
            )
        else:
            _verify_one_source(item, source_dir, manifest)
        record = checked_sources[item["source_filename"]]
        rows.append((
            item["cik"], item["accession_number"], item["security_id"],
            item["sec_accepted_at"], item["filing_date"], item["form"],
            item["source_filename"], item["source_sha256"], record["origin"],
            record["retrieved_at_utc"], str(db.resolve()), st.st_size,
            st.st_mtime_ns, item["matched_facts"], STAGE,
        ))
    return rows


def _write_journal(journal: Path, rows: list[tuple], report: dict) -> tuple[int, int]:
    # A separate journal is the ONLY writable SQLite database. The complete
    # candidate batch is an atomic transaction, with no silent UPSERT.
    journal.parent.mkdir(parents=True, exist_ok=True)
    new_rows = reused_rows = 0
    with closing(sqlite3.connect(journal, timeout=3)) as con:
        con.execute("PRAGMA busy_timeout=3000")
        con.execute("BEGIN IMMEDIATE")
        con.execute(CREATE_EVIDENCE)
        con.execute(CREATE_RUN)
        existing_schema = {r[1] for r in con.execute("PRAGMA table_info(sec_acceptance_evidence)")}
        if not REQUIRED_COLS.issubset(existing_schema):
            raise EvidenceBlocked("EVIDENCE_JOURNAL_SCHEMA_MISMATCH")
        immutable_cols = (
            "cik", "accession_number", "security_id", "sec_accepted_at",
            "filing_date", "form", "source_filename", "source_sha256",
            "origin", "source_retrieved_at_utc", "backup_file",
            "backup_size_bytes", "backup_mtime_ns", "matched_facts", "stage_status",
        )
        timestamp = datetime.now(timezone.utc).isoformat()
        for row in rows:
            old = con.execute(
                "SELECT " + ",".join(immutable_cols) +
                " FROM sec_acceptance_evidence WHERE cik=? AND accession_number=? AND security_id=?",
                row[:3],
            ).fetchone()
            if old is not None:
                if tuple(old) != row:
                    raise EvidenceBlocked("EVIDENCE_CONFLICT_EXISTING_JOURNAL")
                reused_rows += 1
                continue
            con.execute(
                "INSERT INTO sec_acceptance_evidence (" +
                ",".join(immutable_cols) + ",inserted_at_utc) VALUES (" +
                ",".join("?" for _ in range(len(row) + 1)) + ")",
                (*row, timestamp),
            )
            new_rows += 1
        run_id = hashlib.sha256(
            json.dumps({
                "candidate_rows": rows, "scope": (
                    report.get("issuer_offset"), report.get("accession_offset")),
            }, sort_keys=True).encode("utf-8")
        ).hexdigest()
        con.execute(
            "INSERT OR IGNORE INTO sec_acceptance_staging_runs VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, timestamp, report["issuer_offset"], report["accession_offset"],
             len(rows), new_rows, reused_rows,
             report["counts"].get("missing_archival_documents", 0),
             "SOURCE_REVIEW_ONLY_NOT_PIT_CERTIFIED"),
        )
        con.commit()
    return new_rows, reused_rows


def stage_evidence(
    db: Path, source_dir: Path, journal: Path, *,
    execute: bool = False, max_issuers: int = 1,
    max_accessions: int = 1000, max_facts: int = 2000,
    issuer_offset: int = 0, accession_offset: int = 0,
) -> dict:
    if db.is_symlink() or not db.is_file():
        raise EvidenceBlocked("REQUIRES_EXISTING_OFFLINE_DATABASE_BACKUP")
    if source_dir.is_symlink() or not source_dir.is_dir():
        raise EvidenceBlocked("REQUIRES_ORIGINAL_SEC_SOURCE_FOLDER")
    dest = _private_journal_path(db, source_dir, journal)
    report = reconcile(db, source_dir, max_issuers=max_issuers,
                       max_accessions=max_accessions, max_facts=max_facts,
                       issuer_offset=issuer_offset, accession_offset=accession_offset)
    if report["status"].startswith("BLOCKED"):
        raise EvidenceBlocked("SEC_RECONCILIATION_BLOCKED")
    rows = _evidence_rows(report, db, source_dir)
    result = {
        "schema": SCHEMA,
        "status": "PREVIEW_REVIEW_REQUIRED",
        "mode": "STAGE_ONLY" if execute else "READ_ONLY_PREVIEW",
        "journal": str(dest),
        "candidate_accessions": len(rows),
        "new_rows": 0, "reused_rows": 0,
        "source_provenance_manifest_checked": bool(rows),
        "original_sec_acceptance_independently_certified": False,
        "historical_pit_certified": False, "wf9_activated": False,
        "operational_db_modified": False,
        "archival_coverage_complete": report["archival_coverage_complete"],
        "next_issuer_offset": report["next_issuer_offset"],
        "next_accession_offset": report.get("next_accession_offset"),
        "reconciliation_counts": report["counts"],
    }
    if execute and rows:
        n, reused = _write_journal(dest, rows, report)
        result.update(status="EVIDENCE_STAGED_FOR_MANUAL_REVIEW",
                      new_rows=n, reused_rows=reused)
    elif execute:
        result["status"] = "NO_EVIDENCE_ELIGIBLE_NOTHING_WRITTEN"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Offline verified SQLite backup")
    parser.add_argument("--submissions-dir", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True,
                        help="Separate PRIVATE evidence SQLite outside Git and SEC sources")
    parser.add_argument("--execute", action="store_true", help="Write to separate journal only")
    parser.add_argument("--max-issuers", type=int, default=1)
    parser.add_argument("--max-accessions", type=int, default=1000)
    parser.add_argument("--max-facts-per-accession", type=int, default=2000)
    parser.add_argument("--issuer-offset", type=int, default=0)
    parser.add_argument("--accession-offset", type=int, default=0)
    args = parser.parse_args()
    try:
        result = stage_evidence(
            args.db, args.submissions_dir, args.journal, execute=args.execute,
            max_issuers=args.max_issuers, max_accessions=args.max_accessions,
            max_facts=args.max_facts_per_accession,
            issuer_offset=args.issuer_offset, accession_offset=args.accession_offset,
        )
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        parser.exit(2, "SEC_EVIDENCE_STAGE_BLOCKED: " +
                    (str(exc) if isinstance(exc, EvidenceBlocked) else type(exc).__name__) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

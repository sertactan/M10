from __future__ import annotations

"""One-issuer SEC archive pilot: download, verify, stage only in PRIVATE journal.

Default mode is offline, read-only and network-free. Explicit --download uses
the existing conservative SEC collector; explicit --stage writes only an
independent evidence review ledger, NEVER the M10 production database.
"""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3

from scripts.phase14_sec_acceptance_stage import normalize_cik
from scripts.phase14_sec_submissions_collect import (
    _archival_names, _read_existing, _safe_output_dir, _validate_user_agent,
    collect, CollectorBlocked, ROOT,
)
from scripts.phase14_sec_acceptance_evidence_journal import (
    _load_collector_manifest, _private_journal_path, _verify_one_source,
    stage_evidence, EvidenceBlocked,
)

SCHEMA = "MERIDYEN_SEC_OFFLINE_PILOT_WORKFLOW_V1"
COMPLETE_DOWNLOAD = "COMPLETE_SOURCE_DOWNLOADS_NOT_PIT_CERTIFIED"


class PilotBlocked(ValueError):
    pass


def _preflight(db: Path, sources: Path, journal: Path) -> tuple[Path, Path, Path]:
    # Validate BEFORE any network request / filesystem creation.
    if db.is_symlink() or not db.is_file():
        raise PilotBlocked("REQUIRES_EXISTING_OFFLINE_SQLITE_BACKUP")
    backup = db.expanduser().resolve()
    # Explicitly exclude the installed production operational.db. Other names
    # still need user confirmation; we cannot prove a Windows file is a backup.
    normalized = str(backup).replace("\\", "/").lower()
    if (backup.name.lower() == "operational.db"
            or "/s153researchterminal/runtime/" in normalized):
        raise PilotBlocked("LIVE_RUNTIME_DB_NOT_ALLOWED_USE_SEPARATE_BACKUP")
    src = _safe_output_dir(sources, execute=False)
    dest = _private_journal_path(backup, src, journal)
    if src == backup or src in backup.parents or backup in src.parents:
        raise PilotBlocked("DB_AND_SEC_SOURCE_PATHS_OVERLAP")
    if dest == backup:
        raise PilotBlocked("JOURNAL_MUST_NOT_OVERWRITE_DB")
    # Read-only connection; never create a nonexistent DB.
    try:
        with closing(sqlite3.connect(backup.as_uri() + "?mode=ro",
                                     uri=True, timeout=1)) as con:
            con.execute("PRAGMA query_only=ON")
            names = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('security_master','fundamental_facts_source')"
            )}
            if names != {"security_master", "fundamental_facts_source"}:
                raise PilotBlocked("OFFLINE_BACKUP_MISSING_SEC_SCHEMA")
    except sqlite3.Error as exc:
        raise PilotBlocked("OFFLINE_BACKUP_SQLITE_READ_FAILED") from exc
    return backup, src, dest


def _check_saved_sources(folder: Path, cik: str) -> dict:
    """Fail closed unless all declared archives exist and hashes match."""
    if folder.is_symlink() or not folder.is_dir():
        return {"status": "WAITING_FOR_ORIGINAL_SEC_SOURCE_FOLDER",
                "missing_archives": []}
    roots = sorted(
        f.name for f in folder.iterdir() if ROOT.fullmatch(f.name)
    )
    name = "CIK" + cik + ".json"
    if roots and roots != [name]:
        raise PilotBlocked("ONE_ISSUER_PER_PILOT_FOLDER_REQUIRED")
    if not (folder / name).is_file():
        return {"status": "WAITING_FOR_ORIGINAL_SEC_ROOT",
                "missing_archives": []}
    manifest = _load_collector_manifest(folder)
    # An existing root without provenance is not enough to stage acceptance.
    root, root_hash = _read_existing(folder / name, name, cik, manifest.get(name))
    _verify_one_source({
        "source_filename": name, "source_sha256": root_hash, "cik": cik,
    }, folder, manifest)
    archives = _archival_names(root, cik)
    missing = [a for a in archives if not (folder / a).is_file()]
    if missing:
        return {"status": "WAITING_FOR_HISTORICAL_SEC_ARCHIVES",
                "archive_count": len(archives),
                "missing_archives_count": len(missing),
                "missing_archives": missing[:10]}
    for archive in archives:
        _, digest = _read_existing(
            folder / archive, archive, cik, manifest.get(archive)
        )
        _verify_one_source({
            "source_filename": archive, "source_sha256": digest, "cik": cik,
        }, folder, manifest)
    return {
        "status": "SAVED_SOURCES_VERIFIED_BY_LOCAL_HASH_NOT_SEC_CERTIFIED",
        "root_files": 1, "archive_files": len(archives),
        "missing_archives_count": 0, "missing_archives": [],
    }


def pilot(db: Path, sources: Path, journal: Path, *,
          cik: str, download: bool = False, stage: bool = False,
          max_requests: int = 10, daily_budget: int = 60,
          min_interval: float = 1.0, max_accessions: int = 1000) -> dict:
    if not 1 <= max_accessions <= 50_000:
        raise PilotBlocked("MAX_ACCESSIONS_OUT_OF_BOUNDS")
    issuer = normalize_cik(cik)
    backup, folder, dest = _preflight(db, sources, journal)
    result = {
        "schema": SCHEMA,
        "cik": issuer,
        "status": "PREVIEW_ONLY",
        "backup": str(backup),
        "sources": str(folder),
        "journal": str(dest),
        "download_executed": False,
        "journal_modified": False,
        "production_db_modified": False,
        "original_sec_acceptance_certified": False,
        "historical_pit_certified": False,
        "wf9_activated": False,
        "download_result": None,
        "source_check": None,
        "evidence_preview": None,
        "evidence_stage": None,
    }
    if download:
        # Fail before even creating the SEC directory if no identifying UA.
        _validate_user_agent(os.environ.get("SEC_USER_AGENT"))
        run = collect([issuer], folder, execute=True, max_issuers=1,
                      max_requests=max_requests, daily_budget=daily_budget,
                      min_interval=min_interval)
        result["download_executed"] = True
        result["download_result"] = {
            "status": run["status"],
            "files_downloaded": run["files_downloaded"],
            "files_reused": run["files_reused"],
            "requests_reserved_this_run": run["requests_reserved_this_run"],
            "error_code": run.get("error_code"),
        }
        if run["status"] != COMPLETE_DOWNLOAD:
            result["status"] = "DOWNLOAD_STOPPED_RESUME_OR_REVIEW"
            return result
    source_check = _check_saved_sources(folder, issuer)
    result["source_check"] = source_check
    if source_check["status"] != "SAVED_SOURCES_VERIFIED_BY_LOCAL_HASH_NOT_SEC_CERTIFIED":
        result["status"] = source_check["status"]
        return result

    # Stage refuses ambiguous identity, timestamp paradox and missing data.
    preview = stage_evidence(backup, folder, dest, execute=False,
                             max_issuers=1, max_accessions=max_accessions)
    result["evidence_preview"] = {
        "status": preview["status"],
        "candidate_accessions": preview["candidate_accessions"],
        "archival_coverage_complete": preview["archival_coverage_complete"],
        "next_accession_offset": preview["next_accession_offset"],
        "next_issuer_offset": preview["next_issuer_offset"],
        "reconciliation_counts": preview["reconciliation_counts"],
    }
    if (preview["next_accession_offset"] is not None
            or preview["next_issuer_offset"] is not None):
        result["status"] = "REVIEW_PAGINATION_REQUIRED_NO_AUTO_STAGE"
        return result
    if not stage:
        result["status"] = "EVIDENCE_PREVIEW_READY_NO_WRITES"
        return result
    if not preview["candidate_accessions"]:
        result["status"] = "NO_REVIEWABLE_EVIDENCE_NOT_STAGING"
        return result

    staged = stage_evidence(backup, folder, dest, execute=True,
                            max_issuers=1, max_accessions=max_accessions)
    result["journal_modified"] = staged["new_rows"] > 0
    result["evidence_stage"] = {
        "status": staged["status"],
        "new_rows": staged["new_rows"],
        "reused_rows": staged["reused_rows"],
    }
    result["status"] = "PRIVATE_EVIDENCE_REVIEW_STAGED_NOT_CANONICAL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--db", type=Path, required=True,
                        help="OFFLINE backup, never installed operational.db")
    parser.add_argument("--submissions-dir", type=Path, required=True,
                        help="Isolated single-issuer private folder outside public Git")
    parser.add_argument("--journal", type=Path, required=True,
                        help="Separate private SQLite evidence review journal")
    parser.add_argument("--download", action="store_true",
                        help="OPT-IN: fetch missing original SEC JSONs")
    parser.add_argument("--stage", action="store_true",
                        help="OPT-IN: write reviewable evidence to separate journal")
    parser.add_argument("--max-requests", type=int, default=10)
    parser.add_argument("--daily-budget", type=int, default=60)
    parser.add_argument("--min-interval", type=float, default=1.0)
    parser.add_argument("--max-accessions", type=int, default=1000)
    args = parser.parse_args()
    try:
        report = pilot(args.db, args.submissions_dir, args.journal,
                       cik=args.cik, download=args.download, stage=args.stage,
                       max_requests=args.max_requests,
                       daily_budget=args.daily_budget,
                       min_interval=args.min_interval,
                       max_accessions=args.max_accessions)
    except (PilotBlocked, EvidenceBlocked, CollectorBlocked,
            ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(
            2, "SEC_PILOT_BLOCKED: " +
            (str(exc) if isinstance(exc, (PilotBlocked, EvidenceBlocked, CollectorBlocked))
             else type(exc).__name__) + "\n"
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] in (
        "EVIDENCE_PREVIEW_READY_NO_WRITES",
        "PRIVATE_EVIDENCE_REVIEW_STAGED_NOT_CANONICAL",
        "NO_REVIEWABLE_EVIDENCE_NOT_STAGING",
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())

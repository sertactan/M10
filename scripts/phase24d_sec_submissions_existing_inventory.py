"""Phase24d — offline inventory of *existing* SEC submissions files.

No downloads, APIs, database reads/writes or canonical model changes. Only
check specifically scoped local folders, SEC CIK########## submissions JSON
and optional collector manifests. Never misrepresent a local file as
independently authenticated SEC provenance or an issuer/share-class crosswalk.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re

from scripts.phase14_sec_submissions_collect import (
    _validate_document, CollectorBlocked, MAX_INPUT_BYTES, ROOT, ARCHIVE,
)

SCHEMA = "MERIDYEN_PHASE24D_EXISTING_SEC_SUBMISSIONS_INVENTORY_V1"
PRIOR_SCHEMA = "MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1"
LIMIT_ROOTS = 12000
LIMIT_FILES = 30000
LIMIT_MANIFEST_BYTES = 15_000_000
MAX_EXAMPLES = 20


def _cik(value):
    s = str(value or "").strip()
    if s.isascii() and s.isdigit() and 1 <= len(s) <= 10 and int(s) > 0:
        return s.zfill(10)
    return None


def _manifest(folder):
    path = folder / "sec_sources_manifest.json"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT_MANIFEST_BYTES:
        raise ValueError("UNSAFE_SEC_SOURCE_MANIFEST")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("schema") != "MERIDYEN_PHASE14_SEC_SUBMISSIONS_COLLECT_V1"
        or not isinstance(data.get("documents"), dict)):
        raise ValueError("UNRECOGNIZED_SEC_MANIFEST")
    return data["documents"]


def _source(folder, name, manifest):
    path = folder / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        return "MISSING_UNSAFE_OR_OVERSIZED", None
    content = path.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    item = manifest.get(name) if manifest is not None else None
    if item is not None and item.get("sha256") != sha:
        return "MANIFEST_SHA_MISMATCH", None
    expected = ROOT.fullmatch(name) or ARCHIVE.fullmatch(name)
    if expected is None:
        return "INVALID_SEC_SOURCE_NAME", None
    try:
        source = _validate_document(content, name, expected_cik=expected.group(1))
    except (ValueError, TypeError, KeyError, CollectorBlocked):
        return "SEC_JSON_SHAPE_INVALID", None
    if item and item.get("origin") == "FETCHED_FROM_PINNED_SEC_HTTPS_ENDPOINT":
        state = "LOCAL_SCHEMA_HASH_VALID_MANIFEST_CLAIMS_PINNED_FETCH_NOT_INDEPENDENT"
    elif item:
        state = "LOCAL_SCHEMA_HASH_VALID_MANIFEST_NOT_PROOF_OF_SEC_ORIGIN"
    else:
        state = "LOCAL_SCHEMA_VALID_NO_SOURCE_PROVENANCE_MANIFEST"
    return state, source


def _read_phase24(report):
    if report.is_symlink() or not report.is_file() or report.stat().st_size > 30_000_000:
        raise ValueError("PHASE24_REPORT_MISSING_OR_UNSAFE")
    doc = json.loads(report.read_text(encoding="utf-8"))
    if (doc.get("schema") != PRIOR_SCHEMA
        or doc.get("status") != "SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS"
        or doc.get("reconciled_phase19_20_21_23") is not True
        or doc.get("historical_identity_certifications") != 0
        or len(doc.get("candidate_records", [])) != doc.get("simfin_ids_in_window")):
        raise ValueError("PHASE24_REPORT_NOT_VERIFIED")
    ciks = set()
    for candidate in doc["candidate_records"]:
        for c in candidate.get("candidate_CIKs_NOT_verified", []):
            cik = _cik(c)
            if cik:
                ciks.add(cik)
    return ciks


def inventory(phase24, dirs):
    candidates = _read_phase24(phase24)
    checked = []
    counts = Counter()
    issuer_roots = set()
    issuer_with_manifest_complete_archive = set()
    examples = []
    seen_paths = set()
    for folder in dirs:
        folder = Path(folder).expanduser().resolve()
        if folder in seen_paths:
            continue
        seen_paths.add(folder)
        if not folder.is_dir():
            checked.append({"directory":str(folder),"status":"NOT_FOUND_OR_NOT_DIRECTORY"})
            continue
        if folder.is_symlink():
            raise ValueError("SEC_SOURCE_DIRECTORY_SYMLINK")
        manifest = _manifest(folder)
        # Explicit directory only, no recursive disk / entire repo traversal.
        files = sorted(x for x in folder.iterdir()
                       if ROOT.fullmatch(x.name) or ARCHIVE.fullmatch(x.name))
        if len(files) > LIMIT_FILES:
            raise ValueError("SEC_SOURCE_DIRECTORY_EXCEEDS_SCOPED_FILE_LIMIT")
        roots = [x for x in files if ROOT.fullmatch(x.name)]
        if len(roots) > LIMIT_ROOTS:
            raise ValueError("SEC_ROOT_COUNT_EXCEEDS_BOUNDED_LIMIT")
        checked.append({"directory":str(folder),
                        "status":"SCOPED_DIRECTORY_INSPECTED",
                        "root_documents_named":len(roots),
                        "archive_documents_named":len(files)-len(roots),
                        "collector_manifest_present":manifest is not None})
        counts["all_root_filenames_seen"] += len(roots)
        counts["all_archival_filenames_seen"] += len(files)-len(roots)
        for root in roots:
            cik = ROOT.fullmatch(root.name).group(1)
            if cik not in candidates:
                counts["root_issuers_not_in_phase24_candidate_CIKs"] += 1
                continue
            status, doc = _source(folder,root.name,manifest)
            counts["candidate_root_status_"+status] += 1
            if doc is None:
                if len(examples) < MAX_EXAMPLES:
                    examples.append({"CIK":cik,"issue":status})
                continue
            issuer_roots.add(cik)
            archived = doc["filings"].get("files",[])
            expected_names = []
            for item in archived:
                name = item.get("name") if isinstance(item,dict) else None
                if not isinstance(name,str) or not re.fullmatch(
                    rf"CIK{cik}-submissions-\d{{3,}}\.json", name
                ):
                    raise ValueError("ROOT_REFERENCES_INVALID_ARCHIVE")
                expected_names.append(name)
            counts["candidate_manifest_expected_archive_files"] += len(expected_names)
            # A root with zero archives is legitimate; requires original source
            # history recency validation before actual historical data use.
            valid_archives = 0
            issues = []
            for name in set(expected_names):
                state, _ = _source(folder,name,manifest)
                if state.startswith("LOCAL_SCHEMA"):
                    valid_archives += 1
                else:
                    issues.append({"name":name,"status":state})
                    counts["candidate_archive_status_"+state] += 1
            counts["candidate_archive_files_schema_valid"] += valid_archives
            if valid_archives == len(set(expected_names)) and len(set(expected_names)) == len(expected_names):
                issuer_with_manifest_complete_archive.add(cik)
            elif len(examples) < MAX_EXAMPLES:
                examples.append({"CIK":cik,"missing_or_bad_archive_count":len(issues),
                                 "samples":issues[:3]})
    return {
        "schema":SCHEMA,
        "status":"OFFLINE_LOCAL_SEC_SUBMISSIONS_SOURCE_INVENTORY_NOT_PIT_CERTIFIED",
        "phase24_CIK_candidates":len(candidates),
        "scoped_directories":checked,
        "candidate_CIKs_with_locally_schema_valid_root":len(issuer_roots),
        "candidate_CIKs_with_all_root_listed_archives_schema_valid":
            len(issuer_with_manifest_complete_archive),
        "candidate_CIKs_without_local_schema_valid_root_IN_SCOPED_DIRS":
            len(candidates - issuer_roots),
        "source_file_counts":dict(sorted(counts.items())),
        "small_issue_examples":examples,
        "all_possible_computer_directories_searched":False,
        "sec_provenance_independently_verified":False,
        "historical_share_class_CIK_certifications":0,
        "database_modified":False,
        "network_requests":0,
        "paid_api_calls":0,
        "model_training_performed":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime")
    p.add_argument("--phase24",type=Path,
                   default=root/"phase24/simfin_sec_cik_candidates.json")
    p.add_argument("--dir",action="append",type=Path,dest="dirs",
                   help="Explicit existing SEC submissions source folder (repeatable)")
    p.add_argument("--out",type=Path,
                   default=root/"phase24d/sec_submissions_existing_inventory.json")
    args=p.parse_args()
    dirs=args.dirs or [
        Path("E:/Meridyen_SEC/submissions"),
        root/"sec_mirror/submissions", root/"sec_submissions",
    ]
    try:
        data=inventory(args.phase24,dirs)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        staged=args.out.with_suffix(".json.tmp")
        staged.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",
                          encoding="utf-8")
        staged.replace(args.out)
    except (OSError,ValueError,TypeError,KeyError):
        print("PHASE24D_BLOCKED: LOCAL_SEC_SOURCE_OR_PRIOR_EVIDENCE_INVALID")
        return 2
    print(json.dumps({
        "status":data["status"],
        "phase24_CIK_candidates":data["phase24_CIK_candidates"],
        "directories":data["scoped_directories"],
        "candidate_CIKs_with_locally_schema_valid_root":
            data["candidate_CIKs_with_locally_schema_valid_root"],
        "candidate_CIKs_with_all_root_listed_archives_schema_valid":
            data["candidate_CIKs_with_all_root_listed_archives_schema_valid"],
        "candidate_CIKs_without_local_schema_valid_root_IN_SCOPED_DIRS":
            data["candidate_CIKs_without_local_schema_valid_root_IN_SCOPED_DIRS"],
        "source_file_counts":data["source_file_counts"],
        "database_modified":False,"network_requests":0,
        "full_report_file":str(args.out),
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

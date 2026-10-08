from __future__ import annotations

"""Safely download original SEC submissions root and historical archive JSON.

This is a local-only file collector: NO SQLite access, NO backtest activation,
NO live SEC Companyfacts modification, and NO silent replacement of originals.
Default mode is dry-run. External issuer identifiers are explicit and bounded.

Example (after all other SEC import/download jobs finish):
  set SEC_USER_AGENT to an identifying name and actual contact email privately;
  python -m scripts.phase14_sec_submissions_collect --cik 1408075 \
      --out-dir "E:\\Meridyen_SEC\\submissions" --execute
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time

import httpx

from scripts.phase14_sec_acceptance_stage import MAX_INPUT_BYTES, filing_rows, normalize_cik

SCHEMA = "MERIDYEN_PHASE14_SEC_SUBMISSIONS_COLLECT_V1"
HOST = "https://data.sec.gov/submissions/"
ROOT = re.compile(r"CIK(\d{10})\.json\Z")
ARCHIVE = re.compile(r"CIK(\d{10})-submissions-\d{3,}\.json\Z")
CONTACT = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
DEFAULT_MAX_REQUESTS = 20
DEFAULT_DAILY_BUDGET = 60
MAX_ARCHIVES_PER_ISSUER = 250
# Conservative default below SEC's 10 requests/second per-user-IP limit.
MIN_INTERVAL_SECONDS = 0.5
_LOCK_NAME = ".phase14_sec_submissions_collect.lock"


class CollectorBlocked(RuntimeError):
    """No retry or alternate provider after a SEC policy/validation failure."""


def _validate_user_agent(value: str | None) -> str:
    ua = (value or "").strip()
    if len(ua) < 15 or len(ua) > 240 or not CONTACT.search(ua):
        raise ValueError("Set SEC_USER_AGENT to project name and real contact email")
    if "example.com" in ua.lower() or "\n" in ua or "\r" in ua:
        raise ValueError("SEC_USER_AGENT must have a non-placeholder contact")
    return ua


def _validate_name(name: str, *, cik: str | None = None) -> bool:
    m = ROOT.fullmatch(name) or ARCHIVE.fullmatch(name)
    if m is None or (cik is not None and m.group(1) != cik):
        raise ValueError("SEC filename/CIK not allowlisted")
    return ROOT.fullmatch(name) is not None


def _validate_document(raw: bytes, name: str, *, expected_cik: str) -> dict:
    _validate_name(name, cik=expected_cik)
    if not 0 < len(raw) <= MAX_INPUT_BYTES:
        raise CollectorBlocked("SEC_DOCUMENT_SIZE_INVALID")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CollectorBlocked("SEC_DOCUMENT_NOT_JSON") from exc
    if not isinstance(data, dict):
        raise CollectorBlocked("SEC_DOCUMENT_NOT_OBJECT")
    root = ROOT.fullmatch(name) is not None
    if root:
        try:
            parsed_cik = normalize_cik(data.get("cik"))
        except ValueError as exc:
            raise CollectorBlocked("SEC_ROOT_CIK_MISSING_OR_INVALID") from exc
        if parsed_cik != expected_cik:
            raise CollectorBlocked("SEC_ROOT_CIK_MISMATCH")
        filings = data.get("filings")
        if not isinstance(filings, dict) or not isinstance(filings.get("recent"), dict):
            raise CollectorBlocked("SEC_ROOT_FILINGS_INVALID")
        if not isinstance(filings.get("files", []), list):
            raise CollectorBlocked("SEC_ARCHIVE_MANIFEST_INVALID")
    else:
        if "cik" in data:
            try:
                if normalize_cik(data["cik"]) != expected_cik:
                    raise CollectorBlocked("SEC_ARCHIVE_CIK_MISMATCH")
            except ValueError as exc:
                raise CollectorBlocked("SEC_ARCHIVE_CIK_INVALID") from exc
    try:
        filing_rows(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise CollectorBlocked("SEC_FILINGS_ARRAYS_INVALID") from exc
    return data


def _archival_names(root_payload: dict, cik: str) -> list[str]:
    files = root_payload["filings"].get("files", [])
    if len(files) > MAX_ARCHIVES_PER_ISSUER:
        raise CollectorBlocked("SEC_TOO_MANY_ARCHIVAL_DOCUMENTS")
    names: list[str] = []
    seen = set()
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise CollectorBlocked("SEC_ARCHIVE_MANIFEST_INVALID")
        name = item["name"]
        if not ARCHIVE.fullmatch(name) or not name.startswith("CIK" + cik + "-"):
            raise CollectorBlocked("SEC_ARCHIVE_FILENAME_INVALID")
        if name in seen:
            raise CollectorBlocked("SEC_DUPLICATE_ARCHIVE_NAME")
        seen.add(name)
        names.append(name)
    return names


def _read_existing(path: Path, name: str, cik: str, meta: dict | None) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file():
        raise CollectorBlocked("SEC_DOCUMENT_UNSAFE_EXISTING_PATH")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise CollectorBlocked("SEC_DOCUMENT_SIZE_INVALID")
    raw = path.read_bytes()
    parsed = _validate_document(raw, name, expected_cik=cik)
    digest = hashlib.sha256(raw).hexdigest()
    if meta and meta.get("sha256") != digest:
        raise CollectorBlocked("SEC_SAVED_SOURCE_HASH_MISMATCH")
    return parsed, digest


def _fetch_sec_document(name: str, user_agent: str) -> bytes:
    """TLS verification on, fixed HTTPS host, redirects refused, capped response."""
    _validate_name(name)
    with httpx.Client(
        timeout=httpx.Timeout(30.0), follow_redirects=False, trust_env=False
    ) as client:
        with client.stream(
            "GET", HOST + name,
            headers={
                "User-Agent": user_agent, "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            },
        ) as response:
            if response.status_code in (403, 429, 503):
                raise CollectorBlocked("SEC_ACCESS_POLICY_OR_LIMIT_" + str(response.status_code))
            if response.status_code != 200:
                raise CollectorBlocked("SEC_HTTP_STATUS_" + str(response.status_code))
            size = 0
            chunks: list[bytes] = []
            for chunk in response.iter_bytes(65536):
                size += len(chunk)
                if size > MAX_INPUT_BYTES:
                    raise CollectorBlocked("SEC_DOCUMENT_EXCEEDS_SIZE_LIMIT")
                chunks.append(chunk)
            return b"".join(chunks)


def _atomic_bytes(path: Path, content: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise CollectorBlocked("SEC_SOURCE_ALREADY_PRESENT_NOT_OVERWRITING")
    staged = path.with_name(path.name + "." + str(os.getpid()) + ".part")
    if staged.exists() or staged.is_symlink():
        raise CollectorBlocked("SEC_STAGING_FILE_ALREADY_EXISTS")
    try:
        with staged.open("xb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        # No other collector should write while the exclusive lock is held.
        if path.exists() or path.is_symlink():
            raise CollectorBlocked("SEC_SOURCE_RACE_NOT_OVERWRITING")
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _atomic_json(path: Path, data: dict) -> None:
    staged = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    if staged.is_symlink() or path.is_symlink():
        raise CollectorBlocked("SEC_METADATA_PATH_UNSAFE")
    try:
        with staged.open("x", encoding="utf-8") as out:
            json.dump(data, out, indent=2, sort_keys=True, ensure_ascii=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _load_json(path: Path, fallback: dict) -> dict:
    if path.is_symlink():
        raise CollectorBlocked("SEC_METADATA_PATH_UNSAFE")
    if not path.exists():
        return fallback
    if path.stat().st_size > 5_000_000:
        raise CollectorBlocked("SEC_METADATA_SIZE_INVALID")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CollectorBlocked("SEC_METADATA_INVALID")
    return data


def _reserve_budget(path: Path, *, day: str, max_daily: int) -> int:
    record = _load_json(path, {"schema": SCHEMA, "day_utc": day, "attempts": 0})
    if record.get("schema") != SCHEMA:
        raise CollectorBlocked("SEC_BUDGET_SCHEMA_MISMATCH")
    if record.get("day_utc") != day:
        record = {"schema": SCHEMA, "day_utc": day, "attempts": 0}
    used = record.get("attempts")
    if type(used) is not int or used < 0:
        raise CollectorBlocked("SEC_BUDGET_CORRUPT")
    if used >= max_daily:
        raise CollectorBlocked("SEC_LOCAL_DAILY_BUDGET_EXHAUSTED")
    record["attempts"] = used + 1
    _atomic_json(path, record)
    return used + 1


def _safe_output_dir(path: Path, *, execute: bool) -> Path:
    if path.is_symlink():
        raise CollectorBlocked("SEC_OUTPUT_SYMLINK_NOT_ALLOWED")
    folder = path.expanduser().resolve()
    # Never accidentally store financial source archives in a PUBLIC code repo.
    if any((p / ".git").exists() for p in (folder, *folder.parents)):
        raise CollectorBlocked("SEC_OUTPUT_MUST_BE_OUTSIDE_GIT_REPO")
    if execute:
        folder.mkdir(parents=True, exist_ok=True)
    if folder.exists() and not folder.is_dir():
        raise CollectorBlocked("SEC_OUTPUT_IS_NOT_DIRECTORY")
    return folder


def collect(
    ciks: list[str], folder: Path, *,
    execute: bool = False, max_issuers: int = 3,
    max_requests: int = DEFAULT_MAX_REQUESTS,
    daily_budget: int = DEFAULT_DAILY_BUDGET,
    min_interval: float = MIN_INTERVAL_SECONDS,
    user_agent: str | None = None,
) -> dict:
    if not (1 <= max_issuers <= 100 and 1 <= max_requests <= 100
            and 1 <= daily_budget <= 500 and 0.5 <= min_interval <= 60):
        raise ValueError("SEC request/scope bounds invalid")
    issuers = sorted({normalize_cik(cik) for cik in ciks})
    if not issuers or len(issuers) > max_issuers:
        raise ValueError("At least one and at most max_issuers CIKs required")
    out = _safe_output_dir(folder, execute=execute)
    result = {
        "schema": SCHEMA, "mode": "EXECUTE" if execute else "DRY_RUN",
        "status": "DRY_RUN_ONLY" if not execute else "RUNNING",
        "issuer_count": len(issuers), "ciks": issuers,
        "max_requests": max_requests, "daily_budget": daily_budget,
        "min_interval_seconds": min_interval,
        "requests_reserved_this_run": 0, "files_downloaded": 0,
        "files_reused": 0, "files_failed": 0, "last_document": None,
        "out_dir": str(out), "sqlite_modified": False,
        "canonical_pit_certified": False, "wf9_activated": False,
    }
    if not execute:
        # No file creation and NO network in preview mode.
        return result
    ua = _validate_user_agent(user_agent or os.getenv("SEC_USER_AGENT"))
    lock = out / _LOCK_NAME
    if lock.is_symlink():
        raise CollectorBlocked("SEC_COLLECTOR_LOCK_UNSAFE")
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "pid": os.getpid(),
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
            }))
    except FileExistsError as exc:
        raise CollectorBlocked("SEC_COLLECTOR_ALREADY_LOCKED_REVIEW_OWNER") from exc

    manifest_path = out / "sec_sources_manifest.json"
    budget_path = out / "sec_utc_request_budget.json"
    status_path = out / "sec_download_progress.json"
    day = datetime.now(timezone.utc).date().isoformat()
    since_previous_request: float | None = None

    try:
        manifest = _load_json(manifest_path, {"schema": SCHEMA, "documents": {}})
        if manifest.get("schema") != SCHEMA or not isinstance(manifest.get("documents"), dict):
            raise CollectorBlocked("SEC_SOURCE_MANIFEST_CORRUPT")

        def save_progress(stage: str) -> None:
            result["status"] = stage
            result["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
            _atomic_json(status_path, result)

        def get_document(name: str, cik: str) -> dict:
            nonlocal since_previous_request
            _validate_name(name, cik=cik)
            path = out / name
            result["last_document"] = name
            record = manifest["documents"].get(name)
            if path.exists() or path.is_symlink():
                parsed, digest = _read_existing(path, name, cik, record)
                # Reused preexisting files aren't SEC-origin verified by a hash.
                if record is None:
                    manifest["documents"][name] = {
                        "sha256": digest,
                        "origin": "PREEXISTING_LOCAL_SOURCE_NOT_VERIFIED",
                        "size_bytes": path.stat().st_size,
                    }
                    _atomic_json(manifest_path, manifest)
                result["files_reused"] += 1
                save_progress("REUSED_VERIFIED_LOCAL_JSON")
                return parsed
            if record is not None:
                raise CollectorBlocked("SEC_MANIFEST_SOURCE_MISSING_NEVER_REPLACE")
            if result["requests_reserved_this_run"] >= max_requests:
                raise CollectorBlocked("SEC_RUN_REQUEST_BUDGET_EXHAUSTED")
            # Locally persistent budget is RESERVED before HTTP; this avoids
            # untracked retries when interrupted by the Windows scheduler.
            _reserve_budget(budget_path, day=day, max_daily=daily_budget)
            result["requests_reserved_this_run"] += 1
            save_progress("REQUEST_RESERVED")
            if since_previous_request is not None:
                delay = min_interval - (time.monotonic() - since_previous_request)
                if delay > 0:
                    time.sleep(delay)
            since_previous_request = time.monotonic()
            try:
                raw = _fetch_sec_document(name, ua)
            except httpx.HTTPError as exc:
                raise CollectorBlocked("SEC_NETWORK_ERROR_" + type(exc).__name__) from exc
            parsed = _validate_document(raw, name, expected_cik=cik)
            digest = hashlib.sha256(raw).hexdigest()
            _atomic_bytes(path, raw)
            manifest["documents"][name] = {
                "sha256": digest, "size_bytes": len(raw),
                "origin": "FETCHED_FROM_PINNED_SEC_HTTPS_ENDPOINT",
                "url": HOST + name,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_authenticity_independently_verified": False,
            }
            _atomic_json(manifest_path, manifest)
            result["files_downloaded"] += 1
            save_progress("SOURCE_SAVED")
            return parsed

        save_progress("STARTED")
        for cik in issuers:
            root_name = "CIK" + cik + ".json"
            root = get_document(root_name, cik)
            for name in _archival_names(root, cik):
                get_document(name, cik)
        save_progress("COMPLETE_SOURCE_DOWNLOADS_NOT_PIT_CERTIFIED")
        return result
    except (CollectorBlocked, OSError, ValueError, json.JSONDecodeError) as exc:
        result["files_failed"] += 1
        result["error_class"] = type(exc).__name__
        result["error_code"] = str(exc) if isinstance(exc, CollectorBlocked) else type(exc).__name__
        result["status"] = "STOPPED_REVIEW_REQUIRED"
        # On exception, progress save must not shadow the original error.
        try:
            _atomic_json(status_path, result)
        except OSError:
            pass
        return result
    finally:
        # Only a successfully opened exclusive lock is removed here.
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cik", action="append", required=True,
                        help="SEC issuer CIK. Repeat for each issuer; no live DB reads")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true",
                        help="Explicit opt-in; default dry-run is network-free")
    parser.add_argument("--max-issuers", type=int, default=3)
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    parser.add_argument("--daily-budget", type=int, default=DEFAULT_DAILY_BUDGET)
    parser.add_argument("--min-interval", type=float, default=MIN_INTERVAL_SECONDS)
    args = parser.parse_args()
    try:
        result = collect(args.cik, args.out_dir, execute=args.execute,
                         max_issuers=args.max_issuers, max_requests=args.max_requests,
                         daily_budget=args.daily_budget,
                         min_interval=args.min_interval)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["status"] in (
            "DRY_RUN_ONLY", "COMPLETE_SOURCE_DOWNLOADS_NOT_PIT_CERTIFIED"
        ) else 2
    except (CollectorBlocked, ValueError, OSError) as exc:
        parser.exit(2, "SEC_COLLECTION_BLOCKED: " +
                    (str(exc) if isinstance(exc, CollectorBlocked)
                     else type(exc).__name__) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

"""Cache-first, SEC-compliant INOD filing-body collection and private S13 review.

Reads an existing SEC Submissions JSON. Fixed SEC Archive URLs; one GET per
missing body, no retries, no redirects, no alternative hosts, hard stop on
403/429. All filing bytes, receipts and review output stay in the private local
scoring_completion runtime directory, outside every Git worktree.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.scoring_v3_sec_filing_evidence import (
    MAX_BODY_BYTES, SEC_HOST, analyze_filing_body, assess_filing_collection,
    filing_manifest,
)

EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
CONTACT_KEY = "SEC_USER_AGENT"
MIN_SECONDS_BETWEEN_REQUEST_STARTS = 0.5


class FilingPolicyStop(ValueError):
    pass


class _DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise FilingPolicyStop("SEC_REDIRECT_NOT_FOLLOWED")


def _private_cache(path: Path) -> Path:
    root = (Path(os.environ.get("LOCALAPPDATA", "")) /
            "S153ResearchTerminal" / "runtime" / "scoring_completion").resolve()
    candidate = path.expanduser().resolve()
    if (candidate == root or root not in candidate.parents
            or any(part in (".git", "..") for part in candidate.parts)
            or path.is_symlink()):
        raise ValueError("PRIVATE_SCORING_COMPLETION_CACHE_REQUIRED")
    return candidate


def _user_agent(config_path: Path) -> str:
    if config_path.is_symlink() or not config_path.is_file():
        raise ValueError("LOCAL_SEC_CONTACT_CONFIG_REQUIRED")
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        if "=" not in line or line.strip().startswith(("#", ";")):
            continue
        name, val = line.split("=", 1)
        if name.strip() != CONTACT_KEY:
            continue
        contact = val.strip().strip("'\"")
        if not (15 <= len(contact) <= 240 and EMAIL.search(contact)
                and "example" not in contact.lower()
                and "localhost" not in contact.lower()
                and "\n" not in contact and "\r" not in contact):
            raise ValueError("SEC_USER_AGENT_IDENTIFICATION_REQUIRED")
        return contact
    raise ValueError("SEC_USER_AGENT_NOT_CONFIGURED")


def _fetch_body(row: dict, agent: str) -> tuple[int, bytes | None]:
    """Exactly one compliant request. No redirect or fallback after any denial."""
    url = row["source_ref"]
    if not url.startswith(SEC_HOST + "/Archives/edgar/data/"):
        raise ValueError("SEC_URL_NOT_ALLOWED")
    request = Request(url, headers={
        "User-Agent": agent, "Accept": "text/html,text/plain;q=0.9",
        "Accept-Encoding": "identity",
    }, method="GET")
    opener = build_opener(ProxyHandler({}), _DenyRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            status = response.status
            if status != 200:
                return status, None
            raw = response.read(MAX_BODY_BYTES + 1)
    except HTTPError as exc:
        return exc.code, None
    if not raw or len(raw) > MAX_BODY_BYTES:
        raise FilingPolicyStop("SEC_FILING_HTML_SIZE_INVALID")
    return status, raw


def _receipt_path(path: Path) -> Path:
    return path.with_name(path.name + ".receipt.json")


def _read_existing(path: Path, row: dict) -> tuple[bytes, str] | None:
    receipt = _receipt_path(path)
    if not path.exists() and not receipt.exists():
        return None
    if (path.is_symlink() or receipt.is_symlink() or
            not path.is_file() or not receipt.is_file()):
        raise FilingPolicyStop("PARTIAL_OR_UNTRUSTED_CACHED_FILING_BODY")
    raw = path.read_bytes()
    meta = json.loads(receipt.read_text(encoding="utf-8"))
    if (not 0 < len(raw) <= MAX_BODY_BYTES
            or meta.get("source_ref") != row["source_ref"]
            or meta.get("accession") != row["accession"]
            or meta.get("sha256") != sha256(raw).hexdigest()
            or meta.get("bytes") != len(raw)):
        raise FilingPolicyStop("SEC_FILING_BODY_CACHE_HASH_OR_IDENTITY_CHANGED")
    return raw, meta["retrieved_at"]


def _new_cache(path: Path, row: dict, raw: bytes, *, retrieved_at: str) -> None:
    if path.exists() or path.is_symlink() or _receipt_path(path).exists():
        raise FilingPolicyStop("SEC_FILING_BODY_CACHE_CONFLICT")
    path.parent.mkdir(parents=True, exist_ok=True)
    evidence = analyze_filing_body(row, raw, retrieved_at=retrieved_at)
    # Verify parsed SEC HTML before introducing a cache entry.
    if evidence["source_content_sha256"] != sha256(raw).hexdigest():
        raise FilingPolicyStop("SEC_HTML_CONTENT_HASH_MISMATCH")
    with path.open("xb") as stream:
        stream.write(raw)
    receipt = {
        "schema": "M10_V3_PRIVATE_SEC_HTML_CACHE_RECEIPT_V1",
        "accession": row["accession"], "form": row["form"],
        "source_ref": row["source_ref"], "retrieved_at": retrieved_at,
        "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
        "source_authenticity_independently_verified": False,
        "historical_pit_accepted": False,
    }
    with _receipt_path(path).open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)


def collect(submissions: Path, cache: Path, *, contact: Path | None,
            offline: bool, max_downloads: int, as_of: str,
            max_8k: int = 30) -> dict:
    """Bounded cache-first collection. No DB, app installation, score or alert."""
    private = _private_cache(cache)
    if not 0 <= max_downloads <= 30:
        raise ValueError("MAX_DOWNLOADS_0_TO_30_REQUIRED")
    if submissions.is_symlink() or not submissions.is_file():
        raise ValueError("OFFLINE_SEC_SUBMISSIONS_REQUIRED")
    raw_submissions = submissions.read_bytes()
    manifest = filing_manifest(raw_submissions, through=as_of[:10], max_8k=max_8k)
    # Annual and quarterly bodies establish most statement/footnote coverage.
    ordered = sorted(manifest, key=lambda r: (
        0 if r["form"] == "10-K" else 1 if r["form"] == "10-Q" else 2,
        r["filing_date"], r["accession"]))
    available, attempt_count = [], 0
    blocked, skipped = [], []
    agent = None
    last_request_start = None
    for row in ordered:
        name = row["cache_name"]
        destination = private / name
        stored = _read_existing(destination, row)
        if stored is None:
            if offline or attempt_count >= max_downloads:
                skipped.append(row["accession"])
                continue
            if agent is None:
                if contact is None:
                    raise ValueError("SEC_CONTACT_REQUIRED_FOR_DOWNLOAD")
                agent = _user_agent(contact)
            if last_request_start is not None:
                pause = MIN_SECONDS_BETWEEN_REQUEST_STARTS - (time.monotonic() - last_request_start)
                if pause > 0:
                    time.sleep(pause)
            last_request_start = time.monotonic()
            attempt_count += 1
            try:
                status, body = _fetch_body(row, agent)
            except (FilingPolicyStop, URLError, OSError) as exc:
                blocked.append({"accession": row["accession"], "reason": type(exc).__name__})
                break
            if status in (403, 429):
                blocked.append({"accession": row["accession"], "http_status": status,
                                "reason": "SEC_POLICY_DENIAL_NO_RETRY_OR_BYPASS"})
                break
            if status != 200 or body is None:
                blocked.append({"accession": row["accession"], "http_status": status,
                                "reason": "SEC_HTTP_NOT_200_NO_RETRY"})
                continue
            received = datetime.now(timezone.utc).isoformat()
            _new_cache(destination, row, body, retrieved_at=received)
            stored = body, received
        body, retrieved = stored
        available.append(analyze_filing_body(row, body, retrieved_at=retrieved))
    result = assess_filing_collection(manifest, available, as_of=as_of)
    result["source"] = {
        "submissions_file_sha256": sha256(raw_submissions).hexdigest(),
        "official_sec_archive_only": True,
        "source_authenticity_independently_verified": False,
        "private_cache": str(private),
    }
    result["collection"] = {
        "network_requests_this_run": attempt_count,
        "not_requested_or_unavailable_accessions": skipped,
        "download_failures": blocked,
        "no_retry_on_policy_denial": True,
        "offline": offline,
    }
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--submissions", type=Path, required=True)
    p.add_argument("--private-cache", type=Path, required=True)
    p.add_argument("--contact-env", type=Path)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--max-downloads", type=int, default=12)
    p.add_argument("--max-8k", type=int, default=30)
    p.add_argument("--as-of", default=datetime.now(timezone.utc).isoformat())
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    output = _private_cache(args.out)
    if output.exists() or output.is_symlink() or output.suffix.lower() != ".json":
        raise ValueError("NEW_PRIVATE_RESEARCH_REPORT_REQUIRED")
    report = collect(args.submissions, args.private_cache, contact=args.contact_env,
                     offline=args.offline, max_downloads=args.max_downloads,
                     as_of=args.as_of, max_8k=args.max_8k)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"status": report["status"],
                      "body_filing_count": report["body_filing_count"],
                      "expected_filing_count": report["expected_filing_count"],
                      "download_failures": report["collection"]["download_failures"],
                      "requests": report["collection"]["network_requests_this_run"],
                      "S13": report["S13"],
                      "report_sha256": sha256(output.read_bytes()).hexdigest(),
                      "report_path": str(output)}, ensure_ascii=False))
    return 0 if not report["collection"]["download_failures"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the wholly offline Task9 contextual S13 research over 14 cached SEC bodies.

No SEC traffic, no sqlite, no changes to previously saved primary filing files.
Only newly created PRIVATE files inside runtime/scoring_completion/task9_forensic.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from app.task9_forensic_review import SOURCE_SHA, review_contexts

PINNED_V3_REPORT_SHA = "db80442b3e97b79e4a67f5089ebad32c446443f2e2e50957eae2e0dfc5059df4"


def verified_sources(body_root: Path, report_path: Path) -> dict:
    """Require original SEC body, per-filing receipt, 14 unique accessions."""
    if body_root.is_symlink() or report_path.is_symlink() or not report_path.is_file():
        raise ValueError("ORIGINAL_V3_PRIVATE_SOURCE_REQUIRED")
    raw_report = report_path.read_bytes()
    if sha256(raw_report).hexdigest() != PINNED_V3_REPORT_SHA:
        raise ValueError("V3_REPORT_SHA256_CHANGED")
    report = json.loads(raw_report)
    if report.get("body_filing_count") != 14 or report.get("expected_filing_count") != 14:
        raise ValueError("EXPECTED_FOURTEEN_REAL_FILING_BODIES")
    sources = {}
    for row in report["filings"]:
        acc, url = row["accession"], row["source_ref"]
        if (acc in sources or not url.startswith(
                f"https://www.sec.gov/Archives/edgar/data/903651/{acc.replace('-', '')}/")):
            raise ValueError("SEC_ISSUER_URL_OR_ACCESSION_MISMATCH")
        path = body_root / (acc.replace("-", "") + "_" + url.rsplit("/", 1)[-1])
        receipt = Path(str(path) + ".receipt.json")
        if any(p.is_symlink() or not p.is_file() for p in (path, receipt)):
            raise ValueError("ORIGINAL_SEC_BODY_OR_RECEIPT_MISSING")
        raw = path.read_bytes()
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        digest = sha256(raw).hexdigest()
        if (digest != row["source_content_sha256"] or digest != saved["sha256"]
                or len(raw) != saved["bytes"]
                or url != saved["source_ref"]
                or acc != saved["accession"]
                or row["retrieved_at"] != saved["retrieved_at"]):
            raise ValueError("REAL_FILING_RECEIPT_SHA_AND_METADATA_CONFLICT")
        sources[acc] = (row, raw)
    if len(sources) != 14:
        raise ValueError("INVALID_FILING_UNIVERSE")
    return sources


def review_private(body_root: Path, report_path: Path, contract: Path, *,
                   as_of: str) -> dict:
    if (contract.is_symlink() or not contract.is_file()
            or sha256(contract.read_bytes()).hexdigest() != SOURCE_SHA):
        raise ValueError("S13_SOURCE_CONTRACT_HASH_CHANGED")
    sources = verified_sources(body_root, report_path)
    result = review_contexts(sources, as_of=as_of)
    result["inputs"] = {
        "read_only_official_filing_body_cache": str(body_root.resolve()),
        "prior_v3_source_report_sha256": PINNED_V3_REPORT_SHA,
        "original_contract_sha256": SOURCE_SHA,
        "all_14_body_receipts_verified": True,
        "network_requests": 0,
    }
    return result


def _output_path(out: Path) -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise ValueError("LOCALAPPDATA_REQUIRED")
    allowed = (Path(local) / "S153ResearchTerminal" / "runtime"
               / "scoring_completion" / "task9_forensic").resolve()
    target = out.resolve()
    if (target.parent != allowed or target.name not in ("review_v1.json", "review_v2.json")
            or target.exists() or out.is_symlink()
            or Path(str(out) + ".sha256").exists()):
        raise ValueError("ONLY_NEW_PRIVATE_TASK9_OUTPUT_ALLOWED")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-cache", type=Path, required=True)
    parser.add_argument("--v3-report", type=Path, required=True)
    parser.add_argument("--source-contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    destination = _output_path(args.out)
    now = datetime.now(timezone.utc).isoformat()
    result = review_private(args.body_cache, args.v3_report,
                            args.source_contract, as_of=now)
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(payload)
    with Path(str(destination)+".sha256").open("x", encoding="ascii") as stream:
        stream.write(sha256(payload).hexdigest())
    print(json.dumps({
        "status":result["status"], "ticker":"INOD",
        "filing_bodies_verified":result["filing_bodies_verified"],
        "block_context_counts":{k:v["source_verified_findings"] for k,v in result["blocks"].items()},
        "unresolved_anchors":len(result["unresolved_anchors"]),
        "S13":result["S13"],"serious_flag_count":result["serious_flag_count"],
        "network_requests":0,
        "private_report_path":str(destination),
        "report_sha256":sha256(payload).hexdigest(),
    },ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

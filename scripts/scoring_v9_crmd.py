"""CRMD V9 genuine S9 acceptance: pinned SEC files, offline replay and private seal.

Writes only E:/M10/.scoring_v9_private/crmd/report.json and its SHA256 seal;
existing files are re-performed and compared byte-for-byte. Zero network calls.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v9_crmd import (
    CURRENT_10K_URL, PRIOR_10K_URL, PRIOR_BODY_SHA256, calculate,
)
from app.scoring_v8_s9_audit import SOURCE_PINS

PRIVATE = Path("E:/M10/.scoring_v9_private/crmd")
REPORT = PRIVATE / "report.json"
V6_RESPONSES = Path("E:/M10/.scoring_v6_private/task9_jones_eton/responses")
V8_RESPONSES = Path("E:/M10/.scoring_v8_private/task9_jones_v8_piotroski/responses")
V9_RESPONSES = PRIVATE / "task9_jones_v9_crmd" / "responses"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0001410098.json"


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def cached(root: Path, url: str, expected: str) -> bytes:
    digest = _hash(url.encode("utf8"))
    raw_file = root / (digest + ".bin")
    metadata_file = root / (digest + ".json")
    if (not raw_file.is_file() or raw_file.is_symlink()
            or not metadata_file.is_file() or metadata_file.is_symlink()):
        raise ValueError("CRMD_PINNED_OFFICIAL_SEC_CACHE_MISSING:" + url)
    raw = raw_file.read_bytes()
    metadata = json.loads(metadata_file.read_text(encoding="utf8"))
    if (metadata.get("url") != url or metadata.get("http_status") not in (200, 206)
            or metadata.get("sha256") != _hash(raw)
            or _hash(raw) != expected):
        raise ValueError("CRMD_CACHED_OFFICIAL_SOURCE_SHA_OR_URL_INVALID")
    return raw


def sources() -> tuple[bytes, bytes, bytes, bytes]:
    runtime = Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime"
    archive = runtime / "bulk" / "sec" / "companyfacts.zip"
    if not archive.is_file() or archive.is_symlink():
        raise ValueError("CRMD_LOCAL_SEC_COMPANYFACTS_ZIP_REQUIRED")
    with zipfile.ZipFile(archive) as z:
        member = z.getinfo("CIK0001410098.json")
        if member.file_size > 40_000_000:
            raise ValueError("CRMD_ZIP_MEMBER_OVERSIZE")
        facts = z.read(member)
    if _hash(facts) != SOURCE_PINS["CRMD"]["companyfacts"]:
        raise ValueError("CRMD_COMPANYFACTS_PREVIOUS_SHA_PIN_CHANGED")
    submissions = cached(V6_RESPONSES, SUBMISSIONS_URL,
                         SOURCE_PINS["CRMD"]["submissions"])
    current = cached(V8_RESPONSES, CURRENT_10K_URL, SOURCE_PINS["CRMD"]["body"])
    prior = cached(V9_RESPONSES, PRIOR_10K_URL, PRIOR_BODY_SHA256)
    return facts, submissions, current, prior


def sealed_report(receipt: Path = REPORT, *, verify_only: bool = False) -> dict:
    if receipt.resolve() != REPORT.resolve() or receipt.is_symlink():
        raise ValueError("CRMD_PRIVATE_RECEIPT_PATH_REQUIRED")
    # The source-linked computation happens on each invocation, including replay.
    result = calculate(*sources())
    if (result["score_status"] != "REAL_SCORE_ACCEPTED_RESEARCH"
            or result["verified_signals"] != 9 or result["score"] is None):
        raise ValueError("CRMD_FULL_NINE_SIGNAL_ACCEPTANCE_FAILED")
    encoded = (json.dumps(result, indent=2, sort_keys=True,
                          ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    seal = Path(str(receipt) + ".sha256")
    if receipt.is_file():
        if (seal.is_symlink() or not seal.is_file()
                or receipt.read_bytes() != encoded
                or seal.read_text(encoding="ascii").strip() != _hash(encoded)):
            raise ValueError("CRMD_V9_OFFLINE_REPLAY_OR_SEAL_FAILED")
    elif verify_only:
        raise ValueError("CRMD_V9_RECEIPT_MISSING_VERIFY_ONLY")
    else:
        if seal.exists():
            raise ValueError("CRMD_V9_PRIVATE_REPORT_SEAL_COLLISION")
        receipt.parent.mkdir(parents=True, exist_ok=True)
        with receipt.open("xb") as file:
            file.write(encoded)
        with seal.open("x", encoding="ascii") as file:
            file.write(_hash(encoded) + "\n")
    return {"ticker": result["ticker"], "model": result["model"],
            "score_status": result["score_status"], "score": result["score"],
            "signals": result["signals"], "verified_signals": result["verified_signals"],
            "positive_signal_count": result["positive_signal_count"],
            "receipt": str(receipt), "receipt_sha256": _hash(encoded),
            "source_sha256": result["source_sha256"],
            "new_canonical_pit_scores": 0, "network_requests_for_replay": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true",
                        help="Require sealed report already exists; replay original inputs")
    args = parser.parse_args()
    print(json.dumps(sealed_report(verify_only=args.verify_only),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

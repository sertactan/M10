"""Offline SEC source-backed five-year S10 audit and sealed PRIVATE receipt.

Usage: python -B scripts/scoring_v10_s10.py [--verify-only]
Nothing is written to the repository, production DB or Windows executable.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v10_s10 import CRMD_10K, audit_original_archive

PRIVATE = Path("E:/M10/.scoring_v10_private/s10").resolve()
RECEIPT = PRIVATE / "report.json"
CACHE = PRIVATE / "task9_jones_v10_s10" / "responses"


def cached_original(year: int) -> bytes:
    cfg = CRMD_10K[year]
    hash_url = sha256(cfg["url"].encode("utf8")).hexdigest()
    data_path = CACHE / (hash_url + ".bin")
    meta_path = CACHE / (hash_url + ".json")
    if (not data_path.is_file() or data_path.is_symlink()
            or not meta_path.is_file() or meta_path.is_symlink()):
        raise ValueError("S10_CRMD_ORIGINAL_SEC_CACHE_REQUIRED:"+str(year))
    raw = data_path.read_bytes()
    metadata = json.loads(meta_path.read_text(encoding="utf8"))
    if (metadata.get("url") != cfg["url"]
            or metadata.get("http_status") not in (200,206)
            or metadata.get("sha256") != sha256(raw).hexdigest()
            or metadata.get("sha256") != cfg["sha256"]):
        raise ValueError("S10_OFFICIAL_SEC_CACHED_SOURCE_FINGERPRINT_MISMATCH")
    return raw


def calculate() -> dict:
    runtime = Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime"
    archive = runtime / "bulk" / "sec" / "companyfacts.zip"
    if not archive.is_file() or archive.is_symlink():
        raise ValueError("S10_PINNED_ORIGINAL_SEC_BULK_ZIP_REQUIRED")
    return audit_original_archive(archive,
                                  crmd_body22=cached_original(2022),
                                  crmd_body23=cached_original(2023))


def store_or_verify(*, verify_only: bool = False,
                    receipt: Path = RECEIPT) -> dict:
    receipt = Path(receipt)
    if receipt.resolve().parent != PRIVATE or receipt.is_symlink():
        raise ValueError("S10_V10_PRIVATE_RECEIPT_PATH_REQUIRED")
    material = calculate()  # Always recompute the original sources, including replay.
    if material["new_full_research_scores"] != 0:
        raise ValueError("S10_UNPROVEN_FIVE_YEAR_SCORE_PROMOTION")
    encoded = (json.dumps(material, ensure_ascii=False, sort_keys=True,
                          indent=2, allow_nan=False) + "\n").encode("utf8")
    digest = sha256(encoded).hexdigest()
    seal = Path(str(receipt) + ".sha256")
    if receipt.is_file():
        if (not seal.is_file() or seal.is_symlink()
                or receipt.read_bytes() != encoded
                or seal.read_text(encoding="ascii").strip() != digest):
            raise ValueError("S10_V10_OFFLINE_REPLAY_OR_SHA_SEAL_MISMATCH")
    elif verify_only:
        raise ValueError("S10_RECEIPT_REQUIRED_FOR_VERIFY_ONLY")
    else:
        if seal.exists():
            raise ValueError("S10_PRIVATE_RECEIPT_SHA_COLLISION")
        receipt.parent.mkdir(parents=True, exist_ok=True)
        with receipt.open("xb") as f:
            f.write(encoded)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest+"\n")
    return material


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    material = store_or_verify(verify_only=args.verify_only)
    proof = material["original_crmd_receivables_2022_2023"]
    print(json.dumps({
        "schema":material["schema"],
        "full_new_S10_scores":material["new_full_research_scores"],
        "canonical_PIT":material["historical_canonical_PIT_accepted"],
        "fy2026_annual_cfo_available":False,
        "CRMD_2022_AR_official":proof["2022"],
        "CRMD_2023_AR_official":proof["2023"],
        "target_rows":{ticker:{
            "genuine_numeric_design_years":[year for year,v in sr["years"].items()
                  if v["status"]=="REAL_ORIGINAL_SEC_ANNUAL_TCA_DESIGN_DIAGNOSTIC"],
            "FY2025_blockers":sr["years"]["2025"]["missing"],
            "verified_historical_regime_panels":sr["verified_five_year_sic_regime_panels"]}
            for ticker,sr in material["stocks"].items()},
        "receipt":str(RECEIPT),
        "receipt_sha256":sha256((json.dumps(material,ensure_ascii=False,
                sort_keys=True, indent=2,allow_nan=False)+"\n").encode()).hexdigest(),
        "network_requests":0},sort_keys=True,indent=2))


if __name__ == "__main__":
    main()

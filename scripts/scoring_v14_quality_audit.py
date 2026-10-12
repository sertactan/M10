"""Replay sealed original INOD 10-Ks and V12/V13 quality source receipts."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v14_quality_source import audit_quality_sources
from app.scoring_v13_quality_ixbrl import inspect_filing
from scripts.scoring_v13_quality_ixbrl import BODIES

V13 = Path("E:/M10/.master_tasks_v13_private/quality/inod_ixbrl_inventory_v2.json")
V12 = Path("E:/M10/.master_tasks_v12_private/quality/acceptance_audit_v2.json")
OUT = Path("E:/M10/.master_tasks_v14_private/quality/inod_broad_ixbrl_census_v1.json")


def _sealed(path: Path) -> bytes:
    seal = Path(str(path) + ".sha256")
    if path.is_symlink() or seal.is_symlink():
        raise ValueError("PRIVATE_SOURCE_SYMLINK_REJECTED")
    raw = path.read_bytes()
    if seal.read_text("ascii").strip() != sha256(raw).hexdigest():
        raise ValueError("PRIVATE_SOURCE_SEAL_CHANGED")
    return raw


def run(*, verify: bool = False) -> dict:
    v13 = json.loads(_sealed(V13))
    v12 = json.loads(_sealed(V12))
    inspected = [inspect_filing(p, Path(str(p) + ".receipt.json")) for p in BODIES]
    if v13.get("filings") != inspected or v13.get("scope") != "ORIGINAL_FILING_TAG_INVENTORY_ONLY":
        raise ValueError("V13_ORIGINAL_FILING_REPLAY_CHANGED")
    original = [(p.read_bytes(), row) for p, row in zip(BODIES, inspected)]
    result = audit_quality_sources(original, v12)
    result["v13_source_receipt_sha256"] = sha256(V13.read_bytes()).hexdigest()
    result["v12_quality_receipt_sha256"] = sha256(V12.read_bytes()).hexdigest()
    raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    digest = sha256(raw).hexdigest()
    seal = Path(str(OUT) + ".sha256")
    if OUT.is_symlink() or seal.is_symlink():
        raise ValueError("PRIVATE_OUTPUT_SYMLINK_REJECTED")
    if verify or OUT.exists() or seal.exists():
        if not OUT.is_file() or not seal.is_file() or OUT.read_bytes() != raw or seal.read_text("ascii").strip() != digest:
            raise ValueError("V14_QUALITY_REPLAY_OR_SEAL_CHANGED")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("xb") as f:
            f.write(raw)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest + "\n")
    return {"task9": result["task9"], "task10": result["task10"],
            "filing_fact_counts": [r["ix_nonfraction_rows"] for r in result["filings"]],
            "receipt_sha256": digest, "offline_replay": verify}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify", action="store_true")
    print(json.dumps(run(verify=p.parse_args().verify), sort_keys=True))

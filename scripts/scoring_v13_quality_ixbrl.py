"""Write a private iXBRL source inventory for sealed original INOD 10-Ks."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_quality_ixbrl import inspect_filing

BODY_ROOT = Path.home() / "AppData/Local/S153ResearchTerminal/runtime/scoring_completion/v3_filing_bodies"
BODIES = (
    BODY_ROOT / "000110465926020655_inod-20251231x10k.htm",
    BODY_ROOT / "000141057825000194_inod-20241231x10k.htm",
)
OUT = Path("E:/M10/.master_tasks_v13_private/quality/inod_ixbrl_inventory_v2.json")


def run(*, verify: bool = False) -> dict:
    result = {"filings": [inspect_filing(path, Path(str(path)+".receipt.json"))
                          for path in BODIES],
              "S6": None, "B_Q": None, "S13": None, "S14": None,
              "scope": "ORIGINAL_FILING_TAG_INVENTORY_ONLY"}
    if {r["accession"] for r in result["filings"]} != {
            "0001104659-26-020655", "0001410578-25-000194"}:
        raise ValueError("ORIGINAL_INOD_FILING_PAIR_CHANGED")
    raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    digest = sha256(raw).hexdigest()
    seal = OUT.with_name(OUT.name + ".sha256")
    if OUT.is_symlink() or seal.is_symlink():
        raise ValueError("PRIVATE_OUTPUT_SYMLINK_REJECTED")
    if verify or OUT.exists() or seal.exists():
        if not OUT.is_file() or not seal.is_file() or OUT.read_bytes() != raw or seal.read_text("ascii").strip() != digest:
            raise ValueError("V13_IXBRL_REPLAY_OR_SEAL_CHANGED")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("xb") as f:
            f.write(raw)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest + "\n")
    return {"source_filings": len(result["filings"]),
            "short_term_investment_candidate_rows": sum(len(r["short_term_investment_monetary_candidates"])
                                                        for r in result["filings"]),
            "new_S6_score": None, "INOD_S14": None,
            "receipt_sha256": digest, "offline_replay": verify}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify", action="store_true")
    print(json.dumps(run(verify=p.parse_args().verify), sort_keys=True))


if __name__ == "__main__":
    main()

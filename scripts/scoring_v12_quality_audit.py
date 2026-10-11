"""Replay V12 Tasks 9/10 source gates into a private, byte-sealed decision packet."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v12_quality_audit import build_report, verified_json

PRIVATE = Path("E:/M10/.master_tasks_v12_private/quality")
OUTPUT = PRIVATE / "acceptance_audit_v2.json"
S13_FORM = Path("E:/M10/.scoring_v5_private/s13/s13_expert_form_v5.json")
S13_SOURCE = Path("E:/M10/.scoring_v4_private/forensic/review_v4.json")
INOD_S9 = Path("E:/M10/.scoring_v9_private/inod_s9/report.json")
CIKS = {"CRMD": "0001410098", "ETON": "0001710340", "PENG": "0001616533"}


def sealed_read(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or Path(str(path) + ".sha256").is_symlink():
        raise ValueError("PRIVATE_SOURCE_SYMLINK_REJECTED")
    raw = path.read_bytes()
    return verified_json(raw, Path(str(path) + ".sha256").read_bytes()), sha256(raw).hexdigest()


def run(*, verify: bool = False) -> dict:
    form, form_sha = sealed_read(S13_FORM)
    source, source_sha = sealed_read(S13_SOURCE)
    if source_sha != form["source_packet_sha256"] or source.get("preserved_findings_verified") != 27:
        raise ValueError("S13_PARENT_EVIDENCE_PACKET_CHANGED")
    s9, s9_sha = sealed_read(INOD_S9)
    archive = Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip"
    with zipfile.ZipFile(archive) as z:
        sec_raw = {ticker: z.read(f"CIK{cik}.json") for ticker, cik in CIKS.items()}
    packet = build_report(sec_raw, s9, form, form_sha)
    packet["source_receipts"] = {"S13_parent_sha256": source_sha, "INOD_S9_sha256": s9_sha}
    raw = (json.dumps(packet, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    digest = sha256(raw).hexdigest()
    seal = Path(str(OUTPUT) + ".sha256")
    if OUTPUT.is_symlink() or seal.is_symlink():
        raise ValueError("PRIVATE_OUTPUT_SYMLINK_REJECTED")
    if verify or OUTPUT.exists() or seal.exists():
        if not OUTPUT.is_file() or not seal.is_file() or OUTPUT.read_bytes() != raw or seal.read_text("ascii").strip() != digest:
            raise ValueError("V12_QUALITY_OFFLINE_REPLAY_OR_SEAL_FAILED")
    else:
        PRIVATE.mkdir(parents=True, exist_ok=True)
        with OUTPUT.open("xb") as f:
            f.write(raw)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest + "\n")
    return {"status": "SOURCE_AUDITED_NO_NEW_FULL_SCORE", "task9": packet["task9"],
            "task10": packet["task10"], "S13_signed_blocks": packet["S13"]["signed_blocks"],
            "INOD_S14": packet["INOD_S14"]["S14"], "private_packet_sha256": digest,
            "offline_replay": verify}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    print(json.dumps(run(verify=parser.parse_args().verify), sort_keys=True))

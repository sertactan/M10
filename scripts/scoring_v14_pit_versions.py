"""Offline INOD filing-version diagnostic; no canonical PIT promotion."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_pit_reconcile import reconcile
from app.scoring_v14_pit_versions import ACCESSIONS, audit_versions


def run(submissions: Path, submissions_receipt: Path, companyfacts: Path,
        body_paths: dict[str, Path], body_receipts: dict[str, Path],
        phase24k: Path, phase24m: Path, output: Path, *, verify: bool) -> dict:
    sources = (submissions, submissions_receipt, companyfacts, phase24k, phase24m,
               *body_paths.values(), *body_receipts.values())
    if any(path.is_symlink() or not path.is_file() for path in sources):
        raise ValueError("PIT_ORIGINAL_SOURCE_MISSING_OR_SYMLINK")
    submissions_raw = submissions.read_bytes()
    receipt_raw = submissions_receipt.read_bytes()
    administrative = reconcile(submissions_raw, receipt_raw,
                               phase24k.read_bytes(), phase24m.read_bytes())
    bodies = {key: value.read_bytes() for key, value in body_paths.items()}
    receipts = {key: value.read_bytes() for key, value in body_receipts.items()}
    facts_raw = companyfacts.read_bytes()
    before = audit_versions(submissions_raw, receipt_raw, facts_raw, bodies, receipts,
                            as_of="2025-03-01T00:00:00+00:00")
    after = audit_versions(submissions_raw, receipt_raw, facts_raw, bodies, receipts,
                           as_of="2026-03-01T00:00:00+00:00")
    if (administrative["administrative_joins_verified"] != 7
            or administrative["canonical_pit_versions"] != 0
            or before["administrative_acceptance_visible_accessions"] != [ACCESSIONS[0]]
            or after["administrative_acceptance_visible_accessions"] != list(ACCESSIONS)
            or before["changed_comparatives"] != after["changed_comparatives"]):
        raise ValueError("PIT_ADMINISTRATIVE_CHRONOLOGY_MISMATCH")
    result = {"schema": "M10_V14_PIT_VERSION_DIAGNOSTIC_V1",
              "seven_accession_administrative_joins": 7,
              "seven_accession_receipt_sha256": sha256(phase24k.read_bytes()).hexdigest(),
              "march_2025_diagnostic": before, "march_2026_diagnostic": after,
              "canonical_pit_versions": 0, "s16c_normalized_pit_features": 0,
              "criterion_13_versioning_verified": False,
              "reason": "Two comparative versions and filing identity are evidenced; historical public and provider clocks, full 7-filing version chain, and daily issuer map are not."}
    encoded = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    digest = sha256(encoded).hexdigest()
    sidecar = output.with_name(output.name + ".sha256")
    if output.is_symlink() or sidecar.is_symlink():
        raise ValueError("PIT_OUTPUT_SYMLINK_REJECTED")
    if verify:
        if (not output.is_file() or not sidecar.is_file()
                or output.read_bytes() != encoded
                or sidecar.read_text("ascii") != digest + "\n"):
            raise ValueError("PIT_REPLAY_OR_SHA_MISMATCH")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as handle:
            handle.write(encoded)
        with sidecar.open("x", encoding="ascii", newline="\n") as handle:
            handle.write(digest + "\n")
    return {"seven_accession_administrative_joins": 7,
            "changed_fy2024_comparatives": len(before["changed_comparatives"]),
            "canonical_pit_versions": 0, "s16c_normalized_pit_features": 0,
            "report_sha256": digest, "verified": verify}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("submissions", "submissions-receipt", "companyfacts", "phase24k", "phase24m",
                 "body-2024", "body-2024-receipt", "body-2025", "body-2025-receipt", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    body_paths = {ACCESSIONS[0]: args.body_2024, ACCESSIONS[1]: args.body_2025}
    body_receipts = {ACCESSIONS[0]: args.body_2024_receipt,
                     ACCESSIONS[1]: args.body_2025_receipt}
    print(json.dumps(run(args.submissions, args.submissions_receipt, args.companyfacts,
                         body_paths, body_receipts, args.phase24k, args.phase24m,
                         args.out, verify=args.verify), sort_keys=True))


if __name__ == "__main__":
    main()

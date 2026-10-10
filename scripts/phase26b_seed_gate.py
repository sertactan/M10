from __future__ import annotations

"""Fail-closed provenance gate for bundled public reference seeds."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

SCHEMA = "M10_PHASE26B_RELEASE_SEEDS_V1"
EXPECTED = {
    "sec_us_current.csv": ("transport", {"SEC_DIRECT", "SEC_MIRROR_EDGARTOOLS"}, 1000),
    "jp_tr_hk_current.csv": ("source", {"FINANCEDATABASE_MIT_REFERENCE"}, 4000),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_csv(path: Path, field: str, allowed: set[str], minimum: int) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Seed missing or linked: {path.name}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or field not in reader.fieldnames:
            raise ValueError(f"Seed provenance column missing: {path.name}")
        values = set()
        count = 0
        for row in reader:
            values.add(row.get(field, ""))
            count += 1
    if count < minimum or not values or not values <= allowed:
        raise ValueError(f"Unapproved or incomplete seed source: {path.name}")
    return {"file": path.name, "sha256": sha256(path), "rows": count,
            "provenance_values": sorted(values)}


def prepare_test_manifest(directory: Path, notices: Path) -> dict:
    if (directory / "manifest.json").exists():
        raise ValueError("Seed manifest already exists")
    entries = [inspect_csv(directory / name, *params) for name, params in EXPECTED.items()]
    if not notices.is_file():
        raise ValueError("Third-party license notice missing")
    manifest = {"schema": SCHEMA, "status": "PRIVATE_TEST_ONLY",
                "contains_operational_or_user_data": False,
                "release_approved": False,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "notices_sha256": sha256(notices), "entries": entries}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(directory: Path, notices: Path, *, private_test: bool,
           approval: Path | None = None) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema") != SCHEMA or manifest.get("status") != "PRIVATE_TEST_ONLY"
            or manifest.get("contains_operational_or_user_data") is not False
            or manifest.get("release_approved") is not False
            or manifest.get("notices_sha256") != sha256(notices)):
        raise ValueError("Seed manifest is invalid or claims unsupported release approval")
    expected = [inspect_csv(directory / name, *params) for name, params in EXPECTED.items()]
    if manifest.get("entries") != expected:
        raise ValueError("Seed SHA-256, row count, or provenance changed")
    if not private_test:
        if approval is None or not approval.is_file():
            raise ValueError("External distribution approval is required")
        decision = json.loads(approval.read_text(encoding="utf-8"))
        if (decision.get("status") != "APPROVED_FOR_DISTRIBUTION"
                or decision.get("seed_sha256") != {x["file"]: x["sha256"] for x in expected}
                or not decision.get("approver") or not decision.get("license_review_reference")):
            raise ValueError("Distribution approval does not match seed hashes")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare-test", "verify-test", "verify-release"))
    parser.add_argument("--seed-dir", required=True, type=Path)
    parser.add_argument("--notices", required=True, type=Path)
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args()
    if args.action == "prepare-test":
        result = prepare_test_manifest(args.seed_dir, args.notices)
    else:
        result = verify(args.seed_dir, args.notices,
                        private_test=args.action == "verify-test", approval=args.approval)
    print(json.dumps({"status": result["status"], "entries": result["entries"]}, sort_keys=True))


if __name__ == "__main__":
    main()
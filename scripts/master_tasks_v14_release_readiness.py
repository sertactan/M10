"""Audit the existing private test package without changing release gates."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.phase26b_seed_gate import verify


EXPECTED_V13_EXE = "b57b392bf774e2f5a398b429f70a748c9130c1ab0689e20946b5d890ba6be23c"
SENSITIVE_NAMES = re.compile(r"(?:^|[\\/])(?:\.env(?:\..*)?|.*\.(?:db|sqlite|sqlite3|htm|html)|.*companyfacts.*)$", re.I)
SECRET_PATTERN = re.compile(rb"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9_-]{24,}\b)")


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit(package: Path, seeds: Path, notices: Path) -> dict:
    exe = package / "S153ResearchTerminal.exe"
    if not exe.is_file() or digest(exe) != EXPECTED_V13_EXE:
        raise ValueError("V13_ACCEPTED_EXE_HASH_CHANGED")
    manifest = verify(seeds, notices, private_test=True)
    internal = package / "_internal"
    bundled = internal / "data" / "seeds"
    if not bundled.is_dir():
        raise ValueError("BUNDLED_SEEDS_MISSING")
    for name in ("manifest.json", "sec_us_current.csv", "jp_tr_hk_current.csv"):
        if digest(bundled / name) != digest(seeds / name):
            raise ValueError("BUNDLED_SEED_DIFFERS_FROM_APPROVED_TEST_INPUT")
    suspicious = [str(p.relative_to(package)) for p in package.rglob("*")
                  if p.is_file() and SENSITIVE_NAMES.search(str(p.relative_to(package)))]
    config_files = sorted((internal / "config").glob("*"))
    secret_hits = [p.name for p in config_files if p.is_file() and SECRET_PATTERN.search(p.read_bytes())]
    if suspicious or secret_hits:
        raise ValueError(f"PRIVATE_PAYLOAD_OR_SECRET_MARKER:{suspicious}:{secret_hits}")
    try:
        verify(seeds, notices, private_test=False, approval=None)
    except ValueError as exc:
        release_gate_rejection = str(exc)
    else:
        raise ValueError("TEST_SEEDS_UNEXPECTEDLY_PASSED_RELEASE_GATE")
    if release_gate_rejection != "Release requires directly fetched SEC US seed":
        raise ValueError(f"UNEXPECTED_RELEASE_GATE_RESULT:{release_gate_rejection}")
    return {"schema": "M10_V14_WINDOWS_RELEASE_READINESS_V1",
            "v13_executable_sha256": EXPECTED_V13_EXE,
            "seed_manifest_sha256": digest(seeds / "manifest.json"),
            "bundled_seed_manifest_sha256": digest(bundled / "manifest.json"),
            "seed_status": manifest["status"],
            "us_seed_transport": manifest["entries"][0]["provenance_values"],
            "us_seed_snapshot": manifest["entries"][0]["snapshot_date"],
            "bundled_private_payload_paths": suspicious,
            "config_secret_marker_hits": secret_hits,
            "release_gate_rejection": release_gate_rejection,
            "production_candidate": False,
            "deployment_criterion_verified": False,
            "required_before_distribution": ["fresh SEC_DIRECT seed within 30 days",
                                             "seed-hash-bound owner distribution approval",
                                             "new isolated build and installed acceptance",
                                             "live DB backup/rollback plan and separate deployment approval"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--seeds", required=True, type=Path)
    parser.add_argument("--notices", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = audit(args.package, args.seeds, args.notices)
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    seal = sha256(raw).hexdigest()
    sidecar = Path(str(args.out) + ".sha256")
    if args.verify:
        if args.out.read_bytes() != raw or sidecar.read_text("ascii").strip() != seal:
            raise ValueError("RELEASE_READINESS_RECEIPT_CHANGED")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("xb") as stream:
            stream.write(raw)
        with sidecar.open("x", encoding="ascii") as stream:
            stream.write(seal + "\n")
    print(json.dumps({"production_candidate": False, "receipt_sha256": seal,
                      "private_payload_paths": len(result["bundled_private_payload_paths"]),
                      "offline_replay": args.verify}, sort_keys=True))


if __name__ == "__main__":
    main()

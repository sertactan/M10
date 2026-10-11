"""Read-only offline audit of a sealed SEC Submissions capture."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v12_pit_audit import audit_sec_submissions


def report_bytes(report: dict, *, newline: str = "\n") -> bytes:
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").replace("\n", newline).encode("utf-8")


def write_or_verify(out: Path, expected: bytes, *, verify: bool) -> str:
    """Never replace a report or seal; verification replays its exact bytes."""
    sidecar = out.with_name(out.name + ".sha256")
    digest = sha256(expected).hexdigest()
    if verify:
        if out.read_bytes() != expected:
            raise ValueError("PRIVATE_PIT_REPORT_REPLAY_MISMATCH")
        if sidecar.exists():
            if sidecar.read_text(encoding="ascii") != digest + "\n":
                raise ValueError("PRIVATE_PIT_REPORT_SEAL_MISMATCH")
        else:
            with sidecar.open("x", encoding="ascii", newline="\n") as handle:
                handle.write(digest + "\n")
        return digest
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as handle:
        handle.write(expected)
    with sidecar.open("x", encoding="ascii", newline="\n") as handle:
        handle.write(digest + "\n")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--accession", action="append", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true",
                        help="recompute and compare exact report bytes; seal without overwriting")
    args = parser.parse_args()
    report = audit_sec_submissions(args.response.read_bytes(),
                                   json.loads(args.receipt.read_text(encoding="utf-8")),
                                   args.accession, as_of=args.as_of)
    # The earlier Windows text-mode report used CRLF. Accept that exact
    # formatting only when replaying an existing artifact; new reports use LF.
    newline = "\n"
    if args.verify:
        existing = args.out.read_bytes()
        if b"\r\n" in existing:
            newline = "\r\n"
    digest = write_or_verify(args.out, report_bytes(report, newline=newline), verify=args.verify)
    print(json.dumps({"output": str(args.out), "source_sha256": report["source_sha256"],
                      "filings": len(report["rows"]),
                      "accepted_pit_versions": report["accepted_pit_versions"],
                      "report_sha256": digest, "verified": args.verify}))


if __name__ == "__main__":
    main()

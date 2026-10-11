"""Generate a compact, private S1-S3/S15.3 gate audit from an existing report."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring_v12_core_audit import audit_report


def _bytes(report: Path) -> tuple[bytes, dict]:
    result = audit_report(report)
    # Existing Windows audit receipts were written with CRLF by Path.write_text.
    # Pin that byte format so --verify can seal the saved file unchanged.
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").replace("\n", "\r\n")
    return payload.encode("utf-8"), result


def _sidecar(out: Path) -> Path:
    return out.with_name(out.name + ".sha256")


def _check_existing(out: Path, expected: bytes) -> None:
    if out.read_bytes() != expected:
        raise ValueError("saved audit bytes differ from recomputed output")


def _seal(out: Path, expected: bytes) -> None:
    _sidecar(out).write_text(sha256(expected).hexdigest() + "\n", encoding="ascii", newline="\n")


def _verify(out: Path, expected: bytes) -> None:
    _check_existing(out, expected)
    seal = _sidecar(out).read_bytes()
    if seal != (sha256(expected).hexdigest() + "\n").encode("ascii"):
        raise ValueError("SHA-256 sidecar mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true", help="compare saved bytes and SHA-256 seal without writing")
    mode.add_argument("--seal-existing", action="store_true", help="seal an already identical saved output without rewriting it")
    args = parser.parse_args()
    expected, result = _bytes(args.report)
    if args.verify:
        _verify(args.out, expected)
        action = "verified"
    elif args.seal_existing:
        _check_existing(args.out, expected)
        _seal(args.out, expected)
        action = "sealed-existing"
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(expected)
        _seal(args.out, expected)
        action = "written-and-sealed"
    print(f"{action} stocks={result['stock_count']} accepted={result['accepted_count']} sha256={sha256(expected).hexdigest()} output={args.out}")


if __name__ == "__main__":
    main()
